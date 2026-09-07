"""Tests for LearnMate Stage 2 — agents + /api/learn + /api/roadmap/adapt.

Run from learnmate/backend/ with:
    pytest tests/test_agents.py -v

All Granite calls are mocked; no real API credentials are needed.
"""

import json
import uuid
import pytest
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, Base, engine


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def init_test_db():
    """Ensure all tables exist before any test runs."""
    from app.models import student, roadmap  # noqa: F401
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def student_id(client):
    """Create a throw-away student and return its id."""
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/students",
        json={
            "name": "Test Student",
            "email": unique_email,
            "interests": ["Python", "AI"],
            "experience_level": "beginner",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ── Granite mock helpers ───────────────────────────────────────────────────────

def _make_mock_granite(json_payload: Dict[str, Any]):
    """Return an AsyncMock for GraniteService.generate_safe that yields json_payload."""
    mock = AsyncMock(return_value=(json.dumps(json_payload), True))
    return mock


# ── Unit: AssessmentAgent ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_assessment_agent_with_granite():
    from app.agents.assessment import AssessmentAgent
    from app.services.granite import GraniteService

    expected = {
        "detected_skills": ["Python", "pandas"],
        "skill_gaps": ["machine learning", "statistics"],
        "recommended_level": "intermediate",
        "summary": "The student has basic Python skills and is ready to move into ML.",
    }

    agent = AssessmentAgent()
    agent.granite.generate_safe = _make_mock_granite(expected)

    result = await agent.run(
        {
            "student_id": "s1",
            "self_reported_skills": ["Python", "pandas"],
            "goal": "become a machine learning engineer",
            "experience_level": "beginner",
        }
    )

    assert result["granite_used"] is True
    assert result["detected_skills"] == expected["detected_skills"]
    assert result["skill_gaps"] == expected["skill_gaps"]
    assert result["recommended_level"] == "intermediate"
    assert "student_id" in result


@pytest.mark.asyncio
async def test_assessment_agent_granite_not_configured():
    from app.agents.assessment import AssessmentAgent

    agent = AssessmentAgent()
    agent.granite.generate_safe = AsyncMock(return_value=("[Granite not configured]", False))

    result = await agent.run(
        {
            "student_id": "s1",
            "self_reported_skills": ["Python"],
            "goal": "learn data science",
            "experience_level": "beginner",
        }
    )

    assert result["granite_used"] is False
    # Falls back to self_reported_skills
    assert "Python" in result["detected_skills"]


# ── Unit: SkillGapAgent ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_skill_gap_agent_with_granite():
    from app.agents.skill_gap import SkillGapAgent

    expected = {
        "gaps": ["deep learning", "neural networks", "statistics"],
        "priority_skills": ["statistics", "deep learning"],
        "explanation": "The student needs statistics and DL fundamentals first.",
    }

    agent = SkillGapAgent()
    agent.granite.generate_safe = _make_mock_granite(expected)

    result = await agent.run(
        {
            "student_id": "s1",
            "current_skills": ["Python", "pandas"],
            "goal": "build neural networks",
        }
    )

    assert result["granite_used"] is True
    assert result["gaps"] == expected["gaps"]
    assert result["priority_skills"] == expected["priority_skills"]
    assert result["explanation"] == expected["explanation"]


@pytest.mark.asyncio
async def test_skill_gap_agent_fallback():
    from app.agents.skill_gap import SkillGapAgent

    agent = SkillGapAgent()
    agent.granite.generate_safe = AsyncMock(return_value=("not json at all", True))

    result = await agent.run(
        {
            "student_id": "s1",
            "current_skills": ["Python"],
            "goal": "learn AI",
        }
    )

    # Should not crash, and return safe defaults
    assert isinstance(result["gaps"], list)
    assert isinstance(result["priority_skills"], list)


# ── Unit: RoadmapPlannerAgent ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_roadmap_planner_with_granite():
    from app.agents.roadmap_planner import RoadmapPlannerAgent

    expected = {
        "roadmap_title": "Python to ML Engineer Roadmap",
        "courses": [
            {
                "title": "Python Fundamentals",
                "description": "Core Python",
                "difficulty": "beginner",
                "estimated_hours": 10,
                "order_index": 0,
            },
            {
                "title": "Statistics for ML",
                "description": "Probability and stats",
                "difficulty": "intermediate",
                "estimated_hours": 15,
                "order_index": 1,
            },
        ],
    }

    agent = RoadmapPlannerAgent()
    agent.granite.generate_safe = _make_mock_granite(expected)

    result = await agent.run(
        {
            "student_id": "s1",
            "goal": "become an ML engineer",
            "skill_gaps": ["statistics", "ML"],
            "experience_level": "beginner",
            "preferences": {},
        }
    )

    assert result["granite_used"] is True
    assert result["roadmap_title"] == expected["roadmap_title"]
    assert len(result["courses"]) == 2
    assert result["courses"][0]["title"] == "Python Fundamentals"


@pytest.mark.asyncio
async def test_roadmap_planner_normalises_bad_courses():
    from app.agents.roadmap_planner import RoadmapPlannerAgent

    # Granite returns courses without estimated_hours
    expected = {
        "roadmap_title": "Quick Roadmap",
        "courses": [
            {"title": "Intro", "description": "basics", "difficulty": "beginner", "order_index": 0},
        ],
    }

    agent = RoadmapPlannerAgent()
    agent.granite.generate_safe = _make_mock_granite(expected)

    result = await agent.run(
        {"student_id": "s1", "goal": "learn Python", "skill_gaps": [], "experience_level": "beginner", "preferences": {}}
    )

    assert result["courses"][0]["estimated_hours"] == 5.0  # default


# ── Unit: ResourceAgent ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resource_agent_with_granite():
    from app.agents.resources import ResourceAgent

    expected = {
        "resources": [
            {
                "title": "Python Docs",
                "description": "Official Python documentation",
                "url": "https://docs.python.org",
                "provider": "Python.org",
            }
        ]
    }

    agent = ResourceAgent()
    agent.granite.generate_safe = _make_mock_granite(expected)

    result = await agent.run(
        {"topic": "Python basics", "level": "beginner", "preferences": {}}
    )

    assert result["granite_used"] is True
    assert len(result["resources"]) == 1
    assert result["resources"][0]["url"] == "https://docs.python.org"


# ── Unit: ProgressAgent ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_progress_agent_with_granite():
    from app.agents.progress import ProgressAgent

    expected = {
        "recommendations": ["Spend more time on statistics", "Review module 2"],
        "adaptation_summary": "Student is progressing well but needs more stats practice.",
        "should_adapt": False,
    }

    agent = ProgressAgent()
    agent.granite.generate_safe = _make_mock_granite(expected)

    result = await agent.run(
        {
            "student_id": "s1",
            "roadmap_id": "r1",
            "progress_data": [{"course": "Python Fundamentals", "pct": 100}],
            "feedback": "I find statistics hard",
        }
    )

    assert result["granite_used"] is True
    assert result["should_adapt"] is False
    assert len(result["recommendations"]) == 2


@pytest.mark.asyncio
async def test_progress_agent_should_adapt_flag():
    from app.agents.progress import ProgressAgent

    expected = {
        "recommendations": ["Switch to an easier statistics course"],
        "adaptation_summary": "Student is struggling; roadmap adjustment recommended.",
        "should_adapt": True,
    }

    agent = ProgressAgent()
    agent.granite.generate_safe = _make_mock_granite(expected)

    result = await agent.run(
        {
            "student_id": "s1",
            "roadmap_id": "r1",
            "progress_data": [{"course": "Advanced ML", "pct": 10}],
            "feedback": "This is too hard",
        }
    )

    assert result["should_adapt"] is True


# ── Integration: POST /api/learn ──────────────────────────────────────────────

def test_learn_endpoint_full_pipeline(client, student_id):
    """Patch agents' run() via unittest.mock.patch for reliable isolation."""
    assessment_rv = {
        "detected_skills": ["Python", "pandas"],
        "skill_gaps": ["statistics", "deep learning"],
        "recommended_level": "intermediate",
        "summary": "Ready for ML.",
        "granite_used": True,
    }
    skill_gap_rv = {
        "gaps": ["neural networks"],
        "priority_skills": ["statistics"],
        "explanation": "Need stats first.",
        "granite_used": True,
    }
    roadmap_rv = {
        "student_id": student_id,
        "roadmap_title": "ML Engineer Roadmap",
        "courses": [
            {
                "title": "Stats 101",
                "description": "Intro to stats",
                "difficulty": "beginner",
                "estimated_hours": 10,
                "order_index": 0,
            }
        ],
        "granite_used": True,
    }
    resources_rv = {
        "topic": "Stats 101",
        "resources": [
            {
                "title": "Khan Academy Statistics",
                "description": "Free statistics course",
                "url": "https://www.khanacademy.org/math/statistics-probability",
                "provider": "Khan Academy",
            }
        ],
        "granite_used": True,
    }
    progress_rv = {
        "student_id": student_id,
        "roadmap_id": "",
        "recommendations": ["Keep going!"],
        "adaptation_summary": "No changes needed yet.",
        "should_adapt": False,
        "granite_used": True,
    }

    with (
        patch("app.api.learn._assessment_agent.run", new=AsyncMock(return_value=assessment_rv)),
        patch("app.api.learn._skill_gap_agent.run", new=AsyncMock(return_value=skill_gap_rv)),
        patch("app.api.learn._roadmap_agent.run", new=AsyncMock(return_value=roadmap_rv)),
        patch("app.api.learn._resource_agent.run", new=AsyncMock(return_value=resources_rv)),
        patch("app.api.learn._progress_agent.run", new=AsyncMock(return_value=progress_rv)),
    ):
        resp = client.post(
            "/api/learn",
            json={
                "student_id": student_id,
                "goal": "become a machine learning engineer",
                "self_reported_skills": ["Python", "pandas"],
                "experience_level": "beginner",
                "preferences": {"learning_style": "visual"},
            },
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["student_id"] == student_id
    assert data["goal"] == "become a machine learning engineer"
    assert isinstance(data["detected_skills"], list)
    assert isinstance(data["skill_gaps"], list)
    assert isinstance(data["courses"], list)
    assert len(data["courses"]) > 0
    assert isinstance(data["initial_resources"], list)
    assert data["roadmap_id"] is not None
    assert data["roadmap_title"] == "ML Engineer Roadmap"
    assert data["granite_used"] is True


def test_learn_endpoint_student_not_found(client):
    resp = client.post(
        "/api/learn",
        json={
            "student_id": "nonexistent-id",
            "goal": "learn Python",
            "self_reported_skills": [],
            "experience_level": "beginner",
        },
    )
    assert resp.status_code == 404


def test_learn_endpoint_missing_goal(client, student_id):
    resp = client.post(
        "/api/learn",
        json={"student_id": student_id},
    )
    assert resp.status_code == 422  # validation error


# ── Integration: POST /api/roadmap/adapt ─────────────────────────────────────

def test_roadmap_adapt_endpoint_no_adapt(client, student_id):
    """should_adapt=False → 200, no DB changes, adapted_roadmap is null."""
    adapt_rv = {
        "student_id": student_id,
        "roadmap_id": "nonexistent-id",
        "recommendations": ["Keep going"],
        "adaptation_summary": "Student is on track.",
        "should_adapt": False,
        "granite_used": True,
    }

    with patch("app.api.roadmap._progress_agent.run", new=AsyncMock(return_value=adapt_rv)):
        resp = client.post(
            "/api/roadmap/adapt",
            json={
                "student_id": student_id,
                "roadmap_id": "nonexistent-id",
                "feedback": "",
                "progress_data": [{"course": "Python", "pct": 50}],
            },
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["should_adapt"] is False
    assert data["adaptation_summary"] == "Student is on track."
    assert data["adapted_roadmap"] is None
    assert "recommendations" in data
    assert data["granite_used"] is True


def test_roadmap_adapt_endpoint_with_adapt(client, student_id):
    """should_adapt=True with a real roadmap_id → roadmap updated in DB."""
    # First create a roadmap so we have a valid roadmap_id
    from app.database import SessionLocal
    from app.models.roadmap import Roadmap

    db = SessionLocal()
    roadmap = Roadmap(
        student_id=student_id,
        title="Test Roadmap",
        description="Initial description",
        goal="Learn testing",
        status="active",
    )
    db.add(roadmap)
    db.commit()
    roadmap_id = roadmap.id
    db.close()

    adapt_rv = {
        "student_id": student_id,
        "roadmap_id": roadmap_id,
        "recommendations": ["Focus on practical exercises"],
        "adaptation_summary": "Roadmap adjusted to be more hands-on.",
        "should_adapt": True,
        "granite_used": True,
    }

    with patch("app.api.roadmap._progress_agent.run", new=AsyncMock(return_value=adapt_rv)):
        resp = client.post(
            "/api/roadmap/adapt",
            json={
                "student_id": student_id,
                "roadmap_id": roadmap_id,
                "feedback": "I prefer practical exercises",
                "progress_data": [{"course": "Module 1", "pct": 100}],
            },
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["should_adapt"] is True
    assert "Roadmap adjusted" in data["adaptation_summary"]
    # adapted_roadmap is returned with updated status
    assert data["adapted_roadmap"] is not None
    assert data["adapted_roadmap"]["status"] == "adapted"
    # Description now contains adaptation note
    assert "Adaptation" in data["adapted_roadmap"]["description"]
    assert data["granite_used"] is True


# ── Integration: existing endpoints still work ────────────────────────────────

def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_student_create_and_get(client):
    unique_email = f"smoke_{uuid.uuid4().hex[:8]}@test.com"
    create_resp = client.post(
        "/api/students",
        json={
            "name": "Smoke Test",
            "email": unique_email,
            "interests": [],
            "experience_level": "advanced",
        },
    )
    assert create_resp.status_code == 201
    sid = create_resp.json()["id"]

    get_resp = client.get(f"/api/students/{sid}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == sid


def test_assessment_endpoint_still_works(client, student_id):
    assessment_rv = {
        "student_id": student_id,
        "detected_skills": ["Python"],
        "skill_gaps": ["ML"],
        "recommended_level": "beginner",
        "summary": "Ready to start.",
        "granite_used": True,
    }

    with patch("app.api.assessment._agent.run", new=AsyncMock(return_value=assessment_rv)):
        resp = client.post(
            "/api/assessment",
            json={
                "student_id": student_id,
                "self_reported_skills": ["Python"],
                "goal": "learn ML",
                "answers": {},
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["student_id"] == student_id
    assert "detected_skills" in data


# ── Unit: ResourceAgent URL sanitiser ────────────────────────────────────────

def test_resource_agent_url_sanitiser():
    """_sanitise_url keeps trusted domains and drops invented paths."""
    from app.agents.resources import _sanitise_url

    # Trusted root URLs → kept
    assert _sanitise_url("https://coursera.org") == "https://coursera.org"
    assert _sanitise_url("https://www.youtube.com") == "https://www.youtube.com"
    assert _sanitise_url("https://docs.python.org/3/tutorial") == "https://docs.python.org/3/tutorial"
    assert _sanitise_url("https://kaggle.com/learn") == "https://kaggle.com/learn"

    # Invented deep paths on trusted domains → kept (domain is trusted)
    assert _sanitise_url("https://coursera.org/learn/machine-learning-invented-path") is not None

    # Completely unknown domains → None
    assert _sanitise_url("https://myfakesite.example.com/course/123") is None
    assert _sanitise_url("https://totally-invented-resource.io/track/ai") is None

    # Non-http schemes → None
    assert _sanitise_url("ftp://coursera.org/course") is None

    # Empty / null / garbage → None
    assert _sanitise_url("") is None
    assert _sanitise_url(None) is None
    assert _sanitise_url("null") is None
    assert _sanitise_url(12345) is None
