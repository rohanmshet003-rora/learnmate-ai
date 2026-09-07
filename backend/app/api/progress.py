"""Progress tracking endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models.roadmap import Progress, Course
from app.schemas.roadmap import ProgressUpdate, ProgressOut

router = APIRouter(prefix="/progress", tags=["progress"])


@router.post("", response_model=ProgressOut, status_code=201)
async def update_progress(payload: ProgressUpdate, db: Session = Depends(get_db)) -> Progress:
    course = db.query(Course).filter(Course.id == payload.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    record = (
        db.query(Progress)
        .filter(
            Progress.student_id == payload.student_id,
            Progress.course_id == payload.course_id,
        )
        .first()
    )

    if record:
        record.completion_pct = payload.completion_pct
        record.completed = payload.completion_pct >= 100.0
        record.last_activity = datetime.utcnow()
        if payload.notes:
            record.notes = payload.notes
    else:
        record = Progress(
            student_id=payload.student_id,
            course_id=payload.course_id,
            completion_pct=payload.completion_pct,
            completed=payload.completion_pct >= 100.0,
            notes=payload.notes,
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return record
