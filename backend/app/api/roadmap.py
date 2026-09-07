"""Roadmap endpoints — create, retrieve, and adapt roadmaps."""

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.roadmap import Roadmap, Course
from app.schemas.roadmap import (
    RoadmapRequest,
    RoadmapOut,
    AdaptRoadmapRequest,
    AdaptRoadmapResponse,
    CourseOut,
)
from app.agents.roadmap_planner import RoadmapPlannerAgent
from app.agents.progress import ProgressAgent

router = APIRouter(prefix="/roadmap", tags=["roadmap"])
logger = logging.getLogger(__name__)

_planner = RoadmapPlannerAgent()
_progress_agent = ProgressAgent()


@router.post("", response_model=RoadmapOut, status_code=201)
async def create_roadmap(payload: RoadmapRequest, db: Session = Depends(get_db)) -> Roadmap:
    agent_result = await _planner.run(payload.model_dump())

    roadmap = Roadmap(
        student_id=payload.student_id,
        title=agent_result.get("roadmap_title", f"Roadmap: {payload.goal}"),
        description=agent_result.get("message", ""),
        goal=payload.goal,
        status="active",
    )
    db.add(roadmap)
    db.commit()
    db.refresh(roadmap)
    return roadmap


@router.get("/{student_id}", response_model=List[RoadmapOut])
async def get_roadmaps(student_id: str, db: Session = Depends(get_db)) -> List[Roadmap]:
    return db.query(Roadmap).filter(Roadmap.student_id == student_id).all()


@router.post("/adapt", response_model=AdaptRoadmapResponse)
async def adapt_roadmap(
    payload: AdaptRoadmapRequest,
    db: Session = Depends(get_db),
) -> AdaptRoadmapResponse:
    """Run the ProgressAgent to analyse progress, then persist any adaptation.

    When Granite returns should_adapt=True and a roadmap_id is provided:
    - The Roadmap description is updated to record the adaptation summary
      and the updated_at timestamp is refreshed.
    - The response includes the full updated roadmap as `adapted_roadmap`.

    When should_adapt=False, no DB changes are made.
    """
    agent_result = await _progress_agent.run(payload.model_dump())

    should_adapt: bool = agent_result.get("should_adapt", False)
    summary: str = agent_result.get("adaptation_summary", "")
    recommendations: List[str] = agent_result.get("recommendations", [])
    granite_used: bool = agent_result.get("granite_used", False)

    adapted_roadmap_out = None

    if should_adapt and payload.roadmap_id:
        roadmap = db.query(Roadmap).filter(Roadmap.id == payload.roadmap_id).first()
        if roadmap:
            # Persist: append adaptation note to the roadmap description
            existing_desc = roadmap.description or ""
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
            adaptation_note = (
                f"\n\n[Adaptation {timestamp}] {summary}"
            )
            roadmap.description = (existing_desc + adaptation_note).strip()
            roadmap.status = "adapted"
            roadmap.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(roadmap)

            # Build response with updated roadmap
            course_outs = [
                CourseOut(
                    id=c.id,
                    title=c.title,
                    description=c.description,
                    url=c.url,
                    provider=c.provider,
                    difficulty=c.difficulty,
                    order_index=c.order_index,
                    estimated_hours=c.estimated_hours,
                )
                for c in sorted(roadmap.courses, key=lambda x: x.order_index)
            ]
            adapted_roadmap_out = RoadmapOut(
                id=roadmap.id,
                student_id=roadmap.student_id,
                title=roadmap.title,
                description=roadmap.description,
                goal=roadmap.goal,
                status=roadmap.status,
                created_at=roadmap.created_at,
                courses=course_outs,
            )
        else:
            logger.warning(
                "adapt_roadmap: roadmap %s not found — skipping DB update",
                payload.roadmap_id,
            )

    return AdaptRoadmapResponse(
        student_id=payload.student_id,
        roadmap_id=payload.roadmap_id,
        should_adapt=should_adapt,
        adaptation_summary=summary,
        recommendations=recommendations,
        adapted_roadmap=adapted_roadmap_out,
        granite_used=granite_used,
    )
