"""Orchestration endpoint — POST /api/learn.

Runs the full agent pipeline:
  1. AssessmentAgent     — skill profile from self-reported data
  2. SkillGapAgent       — identify missing skills
  3. RoadmapPlannerAgent — generate ordered course roadmap
  4. ResourceAgent       — find resources for the first course
  5. ProgressAgent       — baseline progress analysis (no history yet)

Also persists results to the database:
  - Skill records upserted for the student (AssessmentAgent output)
  - Roadmap + Course records created (RoadmapPlannerAgent output)
"""

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.student import Student, Skill
from app.models.roadmap import Roadmap, Course
from app.schemas.roadmap import (
    LearnRequest,
    LearnResponse,
    CourseOut,
    ResourceOut,
)
from app.agents.assessment import AssessmentAgent
from app.agents.skill_gap import SkillGapAgent
from app.agents.roadmap_planner import RoadmapPlannerAgent
from app.agents.resources import ResourceAgent
from app.agents.progress import ProgressAgent

router = APIRouter(prefix="/learn", tags=["learn"])
logger = logging.getLogger(__name__)

_assessment_agent = AssessmentAgent()
_skill_gap_agent = SkillGapAgent()
_roadmap_agent = RoadmapPlannerAgent()
_resource_agent = ResourceAgent()
_progress_agent = ProgressAgent()


# ── DB helpers ────────────────────────────────────────────────────────────────

def _upsert_skills(db: Session, student_id: str, detected_skills: List[str]) -> None:
    """Create or refresh Skill rows for the student based on detected skills."""
    existing = {
        s.name: s
        for s in db.query(Skill).filter(Skill.student_id == student_id).all()
    }
    for skill_name in detected_skills:
        if not skill_name:
            continue
        if skill_name in existing:
            existing[skill_name].assessed_at = datetime.utcnow()
        else:
            db.add(
                Skill(
                    student_id=student_id,
                    name=skill_name,
                    proficiency=0.5,
                    category="detected",
                    assessed_at=datetime.utcnow(),
                )
            )
    db.commit()


def _create_roadmap_with_courses(
    db: Session,
    student_id: str,
    roadmap_title: str,
    goal: str,
    courses_data: List[dict],
) -> Roadmap:
    """Persist Roadmap + Course records and return the Roadmap ORM object."""
    roadmap = Roadmap(
        student_id=student_id,
        title=roadmap_title,
        description=f"AI-generated roadmap for goal: {goal}",
        goal=goal,
        status="active",
    )
    db.add(roadmap)
    db.flush()  # get roadmap.id without committing

    for course_data in courses_data:
        course = Course(
            roadmap_id=roadmap.id,
            title=course_data.get("title", "Untitled"),
            description=course_data.get("description", ""),
            difficulty=course_data.get("difficulty", "beginner"),
            order_index=course_data.get("order_index", 0),
            estimated_hours=course_data.get("estimated_hours"),
        )
        db.add(course)

    db.commit()
    db.refresh(roadmap)
    return roadmap


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("", response_model=LearnResponse)
async def learn(payload: LearnRequest, db: Session = Depends(get_db)) -> LearnResponse:
    """Run the full LearnMate pipeline and return a combined learning plan."""

    # Verify student exists
    student = db.query(Student).filter(Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    granite_used_any = False

    # ── Step 1: Assessment ────────────────────────────────────────────────────
    assessment_result = await _assessment_agent.run(
        {
            "student_id": payload.student_id,
            "self_reported_skills": payload.self_reported_skills,
            "goal": payload.goal,
            "experience_level": payload.experience_level,
        }
    )
    if assessment_result.get("granite_used"):
        granite_used_any = True

    detected_skills: List[str] = assessment_result.get("detected_skills", payload.self_reported_skills)
    skill_gaps: List[str] = assessment_result.get("skill_gaps", [])
    recommended_level: str = assessment_result.get("recommended_level", payload.experience_level)
    assessment_summary: str = assessment_result.get("summary", "")

    # Persist detected skills
    try:
        _upsert_skills(db, payload.student_id, detected_skills)
    except Exception:
        logger.exception("Failed to upsert skills for student %s", payload.student_id)

    # ── Step 2: Skill Gap ─────────────────────────────────────────────────────
    skill_gap_result = await _skill_gap_agent.run(
        {
            "student_id": payload.student_id,
            "current_skills": detected_skills,
            "goal": payload.goal,
        }
    )
    if skill_gap_result.get("granite_used"):
        granite_used_any = True

    priority_skills: List[str] = skill_gap_result.get("priority_skills", skill_gaps[:5])
    gap_explanation: str = skill_gap_result.get("explanation", "")
    # Merge gaps from both agents
    all_gaps: List[str] = list(
        dict.fromkeys(skill_gaps + skill_gap_result.get("gaps", []))
    )

    # ── Step 3: Roadmap ───────────────────────────────────────────────────────
    roadmap_result = await _roadmap_agent.run(
        {
            "student_id": payload.student_id,
            "goal": payload.goal,
            "skill_gaps": all_gaps,
            "experience_level": recommended_level,
            "preferences": payload.preferences,
        }
    )
    if roadmap_result.get("granite_used"):
        granite_used_any = True

    roadmap_title: str = roadmap_result.get("roadmap_title", f"Learning Roadmap: {payload.goal}")
    courses_data: List[dict] = roadmap_result.get("courses", [])

    # Persist roadmap + courses
    roadmap_obj: Roadmap
    try:
        roadmap_obj = _create_roadmap_with_courses(
            db, payload.student_id, roadmap_title, payload.goal, courses_data
        )
    except Exception:
        logger.exception("Failed to persist roadmap for student %s", payload.student_id)
        # Still return results without a DB-backed roadmap id
        from app.models.roadmap import Roadmap as _R
        roadmap_obj = _R(
            id=None,
            student_id=payload.student_id,
            title=roadmap_title,
            goal=payload.goal,
            status="active",
            courses=[],
        )

    # Build CourseOut list from persisted ORM objects (or raw dicts as fallback)
    if roadmap_obj.id and roadmap_obj.courses:
        course_outs = [
            CourseOut(
                id=c.id,
                title=c.title,
                description=c.description,
                difficulty=c.difficulty,
                order_index=c.order_index,
                estimated_hours=c.estimated_hours,
            )
            for c in sorted(roadmap_obj.courses, key=lambda x: x.order_index)
        ]
    else:
        course_outs = [
            CourseOut(
                id=f"tmp-{i}",
                title=c.get("title", ""),
                description=c.get("description"),
                difficulty=c.get("difficulty", "beginner"),
                order_index=c.get("order_index", i),
                estimated_hours=c.get("estimated_hours"),
            )
            for i, c in enumerate(courses_data)
        ]

    # ── Step 4: Resources (for first course/topic) ────────────────────────────
    first_topic = courses_data[0].get("title", payload.goal) if courses_data else payload.goal
    resource_result = await _resource_agent.run(
        {
            "topic": first_topic,
            "level": recommended_level,
            "preferences": payload.preferences,
        }
    )
    if resource_result.get("granite_used"):
        granite_used_any = True

    initial_resources = [
        ResourceOut(
            title=r.get("title", ""),
            description=r.get("description"),
            url=r.get("url"),
            provider=r.get("provider"),
        )
        for r in resource_result.get("resources", [])
    ]

    # ── Step 5: Baseline Progress Check ───────────────────────────────────────
    # No prior progress — pass empty list to get initial recommendations
    await _progress_agent.run(
        {
            "student_id": payload.student_id,
            "roadmap_id": roadmap_obj.id or "",
            "progress_data": [],
            "feedback": "",
        }
    )

    return LearnResponse(
        student_id=payload.student_id,
        goal=payload.goal,
        detected_skills=detected_skills,
        skill_gaps=all_gaps,
        recommended_level=recommended_level,
        assessment_summary=assessment_summary,
        priority_skills=priority_skills,
        gap_explanation=gap_explanation,
        roadmap_id=roadmap_obj.id,
        roadmap_title=roadmap_title,
        courses=course_outs,
        initial_resources=initial_resources,
        granite_used=granite_used_any,
    )
