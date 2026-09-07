"""Student CRUD endpoints."""

import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.student import Student
from app.schemas.student import StudentCreate, StudentOut

router = APIRouter(prefix="/students", tags=["students"])


@router.post("", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
async def create_student(payload: StudentCreate, db: Session = Depends(get_db)) -> Student:
    existing = db.query(Student).filter(Student.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")

    student = Student(
        name=payload.name,
        email=payload.email,
        interests=json.dumps(payload.interests),
        experience_level=payload.experience_level,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return _hydrate(student)


@router.get("/{student_id}", response_model=StudentOut)
async def get_student(student_id: str, db: Session = Depends(get_db)) -> Student:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    return _hydrate(student)


def _hydrate(student: Student) -> Student:
    """Deserialise JSON-stored list fields before Pydantic serialisation."""
    if isinstance(student.interests, str):
        try:
            student.interests = json.loads(student.interests)
        except (ValueError, TypeError):
            student.interests = []
    return student
