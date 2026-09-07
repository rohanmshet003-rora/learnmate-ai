"""Pydantic schemas for Student and Skill API I/O."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


class SkillBase(BaseModel):
    name: str
    proficiency: float = Field(default=0.0, ge=0.0, le=1.0)
    category: Optional[str] = None


class SkillOut(SkillBase):
    id: int
    assessed_at: datetime

    model_config = {"from_attributes": True}


class StudentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    interests: List[str] = Field(default_factory=list)
    experience_level: str = Field(default="beginner", pattern="^(beginner|intermediate|advanced)$")


class StudentOut(BaseModel):
    id: str
    name: str
    email: str
    interests: List[str] = []
    experience_level: str
    created_at: datetime
    skills: List[SkillOut] = []

    model_config = {"from_attributes": True}
