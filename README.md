# LearnMate AI — Agentic Personalised Learning Pathway

> IBM SkillsBuild / AICTE Problem Statement #12  
> **Complete — Stages 1, 2 & 3**

---

## Project Purpose

LearnMate AI is a full-stack agentic system that understands each student's interests and skill level, dynamically builds a personalised course roadmap using **IBM Granite**, and adapts that roadmap in real time based on progress and feedback.

It addresses **AICTE Problem Statement #12: Agentic AI for Personalized Course Pathways**.

---

## Architecture

```
learnmate/
├── backend/                     # Python FastAPI application
│   ├── app/
│   │   ├── main.py              # FastAPI app factory, lifespan, CORS
│   │   ├── config.py            # Pydantic-Settings — all config from env
│   │   ├── database.py          # SQLAlchemy + SQLite engine/session
│   │   ├── models/
│   │   │   ├── student.py       # Student, Skill ORM models
│   │   │   └── roadmap.py       # Roadmap, Course, Module, Progress ORM models
│   │   ├── schemas/
│   │   │   ├── student.py       # Pydantic I/O schemas for Student
│   │   │   └── roadmap.py       # Pydantic I/O schemas for Roadmap/Assessment/Progress
│   │   ├── services/
│   │   │   └── granite.py       # Reusable IBM Granite async client ★
│   │   ├── agents/              # Five IBM Granite-powered agents
│   │   │   ├── base.py          # Abstract BaseAgent interface
│   │   │   ├── assessment.py    # Skill profile from self-reported data
│   │   │   ├── skill_gap.py     # Missing-skill identification
│   │   │   ├── roadmap_planner.py  # Ordered curriculum generation
│   │   │   ├── resources.py     # Curated resource suggestions (verified URLs)
│   │   │   └── progress.py      # Progress analysis + adaptation recommendations
│   │   └── api/
│   │       ├── health.py        # GET  /api/health
│   │       ├── students.py      # POST /api/students · GET /api/students/{id}
│   │       ├── assessment.py    # POST /api/assessment
│   │       ├── roadmap.py       # POST /api/roadmap · GET · POST /adapt
│   │       ├── progress.py      # POST /api/progress
│   │       └── learn.py         # POST /api/learn (full pipeline)
│   ├── tests/
│   │   └── test_agents.py       # 18 unit + integration tests
│   ├── requirements.txt
│   ├── pytest.ini
│   └── .env.example
└── frontend/                    # Vite + React 19 SPA
    ├── src/
    │   ├── App.jsx              # Full 3-step UI (Profile → Goal → Dashboard)
    │   ├── App.css              # Responsive design system
    │   └── index.css
    ├── .env.example
    └── package.json
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9+, FastAPI 0.115, Uvicorn |
| ORM | SQLAlchemy 2.x |
| Validation | Pydantic v2, pydantic-settings |
| Database | SQLite (development / MVP) |
| AI Model | IBM Granite (`ibm/granite-4-h-small`) |
| AI Platform | IBM watsonx.ai REST API |
| Frontend | React 19, Vite 8 |
| HTTP client | HTTPX (async) |
| Tests | pytest, pytest-asyncio |

---

## Agent Pipeline

Each agent extends `BaseAgent` and calls `self.granite.generate_safe()` — the single shared IBM Granite client.

| Agent | Input | IBM Granite task |
|-------|-------|-----------------|
| **AssessmentAgent** | skills, goal, level | Analyses skills vs goal → `detected_skills`, `skill_gaps`, `recommended_level`, `summary` |
| **SkillGapAgent** | current skills, goal | Identifies missing skills → `gaps`, `priority_skills`, `explanation` |
| **RoadmapPlannerAgent** | goal, gaps, level | Designs 4–6 ordered courses → `roadmap_title`, `courses[]` |
| **ResourceAgent** | topic, level | Suggests 3–5 resources → `resources[]` with verified-domain URLs only |
| **ProgressAgent** | progress_data, feedback | Analyses completion → `recommendations`, `adaptation_summary`, `should_adapt` |

`POST /api/learn` runs all five agents in sequence and persists results to SQLite.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/health` | System + Granite status |
| `POST` | `/api/students` | Create student profile |
| `GET`  | `/api/students/{id}` | Get student profile + skills |
| `POST` | `/api/assessment` | Run skill assessment agent |
| `POST` | `/api/roadmap` | Generate roadmap via planner agent |
| `GET`  | `/api/roadmap/{student_id}` | Get all roadmaps for a student |
| `POST` | `/api/roadmap/adapt` | Analyse progress + persist adaptation when `should_adapt=true` |
| `POST` | `/api/progress` | Record course completion percentage |
| `POST` | `/api/learn` | **Full pipeline** — all 5 agents in one call |

Interactive docs: `http://localhost:8000/docs`

---

## Environment Variables

Copy `learnmate/backend/.env.example` → `learnmate/backend/.env` and fill in values.

| Variable | Default | Description |
|----------|---------|-------------|
| `GRANITE_API_KEY` | *(required)* | IBM Cloud API key |
| `IBM_PROJECT_ID` | *(required)* | watsonx.ai project ID |
| `GRANITE_MODEL_ID` | `ibm/granite-4-h-small` | Granite model ID |
| `GRANITE_URL` | `https://us-south.ml.cloud.ibm.com/ml/v1/text/generation` | watsonx.ai endpoint |
| `GRANITE_API_VERSION` | `2023-05-29` | API version date |
| `DATABASE_URL` | `sqlite:///./learnmate.db` | SQLAlchemy database URL |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Allowed CORS origins |

> **Security:** Never commit `.env`. API keys must never appear in source code or the frontend.  
> The `.gitignore` in `learnmate/backend/` excludes `.env`, `*.db`, `venv/`, and `*.log`.

---

## IBM Granite Integration

The client lives in [`app/services/granite.py`](learnmate/backend/app/services/granite.py).

**How it works:**

1. On first call, `GraniteService` exchanges `GRANITE_API_KEY` for an IAM bearer token (`iam.cloud.ibm.com`).
2. The token is used to `POST` to the watsonx.ai text generation REST endpoint.
3. Token is cached in memory; a 401 response clears the cache and re-authenticates automatically.
4. `generate_safe(prompt)` returns `(text, granite_used: bool)` — returns a safe fallback when credentials are absent rather than raising, so the app runs without credentials in development.

All five agents call `generate_safe`. Every API response includes `"granite_used": true/false`.

**URL safety (ResourceAgent):** Resource URLs suggested by Granite are validated against a curated list of 35+ trusted learning platform domains (`coursera.org`, `kaggle.com`, `docs.python.org`, etc.). Any URL from an unknown domain is replaced with `null` — invented deep-links are never shown as real resources.

---

## Local Setup

### Prerequisites

- Python 3.9+
- Node.js 18+

### Backend

```bash
cd learnmate/backend

# Create and activate virtualenv
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env — set GRANITE_API_KEY and IBM_PROJECT_ID

# Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd learnmate/frontend

npm install
npm run dev
# → http://localhost:5173
```

### Run tests

```bash
cd learnmate/backend
source venv/bin/activate
pytest tests/ -v
# → 18 passed
```

### Health check

```bash
curl http://localhost:8000/api/health
```

```json
{
  "status": "ok",
  "app": "LearnMate AI",
  "granite_configured": true,
  "granite_model": "ibm/granite-4-h-small"
}
```

---

## Frontend Flow

The SPA has three steps, each connected to a real backend endpoint:

| Step | UI | API call |
|------|----|---------|
| **1 · Profile** | Name, email, interests, level | `POST /api/students` |
| **2 · Goal** | Enter learning goal; 5-agent spinner | `POST /api/learn` |
| **3 · Dashboard** | Assessment, skill gaps, roadmap, resources, progress sliders, AI adaptation | `POST /api/progress` + `POST /api/roadmap/adapt` |

---

## Roadmap Adaptation

When the "Analyse & adapt roadmap" button is clicked:

1. Frontend sends current course progress percentages + optional feedback to `POST /api/roadmap/adapt`.
2. `ProgressAgent` prompts IBM Granite with the real progress data.
3. If Granite returns `should_adapt: true`, the backend:
   - Appends an adaptation note (with timestamp) to the `Roadmap.description` column.
   - Sets `Roadmap.status = "adapted"`.
   - Returns the full updated roadmap in `adapted_roadmap`.
4. The frontend displays the recommendations and confirms the update was persisted.

---

## Stages

| Stage | Focus | Status |
|-------|-------|--------|
| 1 | Foundation — FastAPI, SQLite, Granite client, agent skeletons, API structure | ✅ Complete |
| 2 | Intelligence — full Granite agent implementations, `/api/learn` pipeline, DB persistence | ✅ Complete |
| 3 | Frontend — connected React SPA, live progress tracking, AI adaptation dashboard | ✅ Complete |
