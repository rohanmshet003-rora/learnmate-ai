"""Pydantic schemas for Roadmap, Assessment, and Progress API I/O."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ── Assessment ──────────────────────────────────────────────────────────────

class AssessmentRequest(BaseModel):
    student_id: str
    answers: dict = Field(default_factory=dict)
    self_reported_skills: List[str] = Field(default_factory=list)
    goal: str = ""


class AssessmentResult(BaseModel):
    student_id: str
    detected_skills: List[str]
    skill_gaps: List[str]
    recommended_level: str
    summary: str
    granite_used: bool = False


# ── Roadmap ──────────────────────────────────────────────────────────────────

class RoadmapRequest(BaseModel):
    student_id: str
    goal: str = Field(..., min_length=3)
    preferences: dict = Field(default_factory=dict)


class CourseOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    url: Optional[str] = None
    provider: Optional[str] = None
    difficulty: str
    order_index: int
    estimated_hours: Optional[float] = None

    model_config = {"from_attributes": True}


class RoadmapOut(BaseModel):
    id: str
    student_id: str
    title: str
    description: Optional[str] = None
    goal: Optional[str] = None
    status: str
    created_at: datetime
    courses: List[CourseOut] = []

    model_config = {"from_attributes": True}


# ── Progress ─────────────────────────────────────────────────────────────────

class ProgressUpdate(BaseModel):
    student_id: str
    course_id: str
    completion_pct: float = Field(..., ge=0.0, le=100.0)
    notes: Optional[str] = None


class ProgressOut(BaseModel):
    id: int
    student_id: str
    course_id: str
    completed: bool
    completion_pct: float
    last_activity: datetime

    model_config = {"from_attributes": True}


# ── Adapt Roadmap ─────────────────────────────────────────────────────────────

class AdaptRoadmapRequest(BaseModel):
    student_id: str
    roadmap_id: str
    feedback: str = ""
    progress_data: List[dict] = Field(default_factory=list)


class AdaptRoadmapResponse(BaseModel):
    student_id: str
    roadmap_id: str
    should_adapt: bool
    adaptation_summary: str
    recommendations: List[str] = Field(default_factory=list)
    # Populated only when should_adapt=True and a roadmap was found
    adapted_roadmap: Optional["RoadmapOut"] = None
    granite_used: bool = False


# ── Learn (orchestration) ─────────────────────────────────────────────────────

class LearnRequest(BaseModel):
    """Input for the POST /api/learn orchestration endpoint."""

    student_id: str
    goal: str = Field(..., min_length=3)
    self_reported_skills: List[str] = Field(default_factory=list)
    experience_level: str = Field(default="beginner", pattern="^(beginner|intermediate|advanced)$")
    preferences: dict = Field(default_factory=dict)


class ResourceOut(BaseModel):
    title: str
    description: Optional[str] = None
    url: Optional[str] = None
    provider: Optional[str] = None


class LearnResponse(BaseModel):
    """Combined output from the full agent pipeline."""

    student_id: str
    goal: str

    # Assessment
    detected_skills: List[str] = Field(default_factory=list)
    skill_gaps: List[str] = Field(default_factory=list)
    recommended_level: str = "beginner"
    assessment_summary: str = ""

    # Skill gap
    priority_skills: List[str] = Field(default_factory=list)
    gap_explanation: str = ""

    # Roadmap
    roadmap_id: Optional[str] = None
    roadmap_title: str = ""
    courses: List[CourseOut] = Field(default_factory=list)

    # Resources (for the first course / topic)
    initial_resources: List[ResourceOut] = Field(default_factory=list)

    # Meta
    granite_used: bool = False
