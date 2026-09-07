import { useState, useEffect, useCallback } from 'react'
import './App.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

// ── tiny API helpers ─────────────────────────────────────────────────────────

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

const post = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body) })
const get  = (path)       => api(path)

// ── small reusable components ────────────────────────────────────────────────

function Badge({ type, children }) {
  return <span className={`badge ${type}`}>{children}</span>
}

function Spinner({ label = 'Loading…' }) {
  return (
    <div className="spinner-wrap">
      <div className="spinner" />
      <p className="muted">{label}</p>
    </div>
  )
}

function ErrorBanner({ message, onDismiss }) {
  if (!message) return null
  return (
    <div className="error-banner" role="alert">
      <span>⚠ {message}</span>
      {onDismiss && (
        <button className="btn-ghost" onClick={onDismiss} aria-label="Dismiss error">✕</button>
      )}
    </div>
  )
}

function ProgressBar({ pct }) {
  const clamped = Math.min(100, Math.max(0, pct || 0))
  return (
    <div className="progress-track">
      <div className="progress-fill" style={{ width: `${clamped}%` }} />
    </div>
  )
}

function TagList({ tags, emptyText = 'None' }) {
  if (!tags || tags.length === 0) return <span className="muted">{emptyText}</span>
  return (
    <div className="tag-list">
      {tags.map((t, i) => <span key={`${t}-${i}`} className="tag">{t}</span>)}
    </div>
  )
}

// ── Step 1: Profile form ──────────────────────────────────────────────────────

const LEVELS = ['beginner', 'intermediate', 'advanced']

function ProfileForm({ onCreated }) {
  const [form, setForm] = useState({
    name: '', email: '', interests: '', experience_level: 'beginner',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!form.name.trim() || !form.email.trim()) {
      setError('Name and email are required.')
      return
    }
    setLoading(true)
    try {
      const interestList = form.interests
        .split(',')
        .map(s => s.trim())
        .filter(Boolean)
      const student = await post('/students', {
        name: form.name.trim(),
        email: form.email.trim(),
        interests: interestList,
        experience_level: form.experience_level,
      })
      onCreated(student)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card profile-card">
      <h2>Create your profile</h2>
      <p className="muted" style={{ marginBottom: 20 }}>
        Tell us about yourself so IBM Granite can personalise your learning path.
      </p>
      <ErrorBanner message={error} onDismiss={() => setError('')} />
      <form onSubmit={handleSubmit} className="form">
        <label>
          <span>Full name</span>
          <input
            type="text"
            value={form.name}
            onChange={e => set('name', e.target.value)}
            placeholder="e.g. Priya Patel"
            required
          />
        </label>
        <label>
          <span>Email</span>
          <input
            type="email"
            value={form.email}
            onChange={e => set('email', e.target.value)}
            placeholder="you@example.com"
            required
          />
        </label>
        <label>
          <span>Interests <span className="muted">(comma-separated)</span></span>
          <input
            type="text"
            value={form.interests}
            onChange={e => set('interests', e.target.value)}
            placeholder="e.g. Python, Data Science, AI"
          />
        </label>
        <label>
          <span>Experience level</span>
          <select value={form.experience_level} onChange={e => set('experience_level', e.target.value)}>
            {LEVELS.map(l => <option key={l} value={l}>{l.charAt(0).toUpperCase() + l.slice(1)}</option>)}
          </select>
        </label>
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Creating…' : 'Create profile →'}
        </button>
      </form>
    </div>
  )
}

// ── Step 2: Goal form ─────────────────────────────────────────────────────────

function GoalForm({ student, onLearned, onBack }) {
  const [goal, setGoal] = useState('')
  const [skills, setSkills] = useState(student.interests?.join(', ') || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!goal.trim() || goal.trim().length < 3) {
      setError('Please enter a goal (at least 3 characters).')
      return
    }
    setLoading(true)
    try {
      const skillList = skills.split(',').map(s => s.trim()).filter(Boolean)
      const result = await post('/learn', {
        student_id: student.id,
        goal: goal.trim(),
        self_reported_skills: skillList,
        experience_level: student.experience_level,
        preferences: {},
      })
      onLearned(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="card center-card">
        <Spinner label="IBM Granite is building your personalised roadmap…" />
        <p className="muted" style={{ marginTop: 12, textAlign: 'center', fontSize: '0.85rem' }}>
          Running 5 AI agents: Assessment → Skill Gap → Roadmap → Resources → Progress
        </p>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2>What do you want to learn?</h2>
          <p className="muted">Hi {student.name} — tell IBM Granite your goal.</p>
        </div>
        <button className="btn-ghost" onClick={onBack}>← Back</button>
      </div>
      <ErrorBanner message={error} onDismiss={() => setError('')} />
      <form onSubmit={handleSubmit} className="form">
        <label>
          <span>Learning goal</span>
          <input
            type="text"
            value={goal}
            onChange={e => setGoal(e.target.value)}
            placeholder="e.g. Become a Machine Learning Engineer"
            required
          />
        </label>
        <label>
          <span>Your current skills <span className="muted">(comma-separated)</span></span>
          <input
            type="text"
            value={skills}
            onChange={e => setSkills(e.target.value)}
            placeholder="e.g. Python, Mathematics"
          />
        </label>
        <button type="submit" className="btn-primary">
          Build my roadmap →
        </button>
      </form>
    </div>
  )
}

// ── Step 3: Dashboard ─────────────────────────────────────────────────────────

function CourseCard({ course, progress, saving, onProgressUpdate }) {
  const pct = progress?.completion_pct ?? 0
  const done = pct >= 100

  function handleSlider(e) {
    onProgressUpdate(course.id, Number(e.target.value))
  }

  return (
    <div className={`course-card ${done ? 'done' : ''} ${saving ? 'saving' : ''}`}>
      <div className="course-header">
        <span className="course-order">#{course.order_index + 1}</span>
        <div className="course-info">
          <strong>{course.title}</strong>
          {course.description && <p className="muted course-desc">{course.description}</p>}
          <div className="course-meta">
            <Badge type={course.difficulty}>{course.difficulty}</Badge>
            {course.estimated_hours && (
              <span className="muted">{course.estimated_hours}h</span>
            )}
            {done && <Badge type="ok">✓ Complete</Badge>}
          </div>
        </div>
      </div>
      <ProgressBar pct={pct} />
      <div className="slider-row">
        <span className="muted" aria-live="polite">{Math.round(pct)}%{saving ? ' …' : ''}</span>
        <input
          type="range"
          min={0}
          max={100}
          step={5}
          value={Math.round(pct)}
          onChange={handleSlider}
          className="slider"
          aria-label={`Progress for ${course.title}`}
        />
      </div>
    </div>
  )
}

function ResourceCard({ resource }) {
  return (
    <div className="resource-card">
      <div className="resource-info">
        <strong>{resource.title}</strong>
        {resource.provider && <Badge type="provider">{resource.provider}</Badge>}
      </div>
      {resource.description && <p className="muted resource-desc">{resource.description}</p>}
      {resource.url && (
        <a href={resource.url} target="_blank" rel="noopener noreferrer" className="resource-link">
          Open resource →
        </a>
      )}
    </div>
  )
}

function Dashboard({ student, learnData, onReset }) {
  const [progressMap, setProgressMap] = useState({})   // course_id → ProgressOut
  const [savingId, setSavingId]       = useState(null)
  const [adaptation, setAdaptation]   = useState(null)
  const [adapting, setAdapting]       = useState(false)
  const [adaptError, setAdaptError]   = useState('')

  const courses = learnData.courses || []

  async function handleProgressUpdate(courseId, pct) {
    setSavingId(courseId)
    try {
      const updated = await post('/progress', {
        student_id: student.id,
        course_id: courseId,
        completion_pct: pct,
      })
      setProgressMap(m => ({ ...m, [courseId]: updated }))
    } catch (err) {
      console.error('Progress update failed:', err.message)
    } finally {
      setSavingId(null)
    }
  }

  async function handleAdapt() {
    setAdapting(true)
    setAdaptError('')
    setAdaptation(null)
    try {
      const progressData = courses.map(c => ({
        course: c.title,
        pct: progressMap[c.id]?.completion_pct ?? 0,
      }))
      const result = await post('/roadmap/adapt', {
        student_id: student.id,
        roadmap_id: learnData.roadmap_id || '',
        progress_data: progressData,
        feedback: '',
      })
      setAdaptation(result)
    } catch (err) {
      setAdaptError(err.message)
    } finally {
      setAdapting(false)
    }
  }

  const completedCount = Object.values(progressMap).filter(p => p.completion_pct >= 100).length
  const overallPct = courses.length > 0
    ? courses.reduce((sum, c) => sum + (progressMap[c.id]?.completion_pct ?? 0), 0) / courses.length
    : 0

  return (
    <div className="dashboard">
      {/* Header */}
      <div className="dash-header">
        <div>
          <h2>{learnData.roadmap_title}</h2>
          <p className="muted">
            {student.name} · {learnData.recommended_level} level
            {learnData.granite_used && <Badge type="granite"> ✦ IBM Granite</Badge>}
          </p>
        </div>
        <button className="btn-ghost" onClick={onReset}>Start over</button>
      </div>

      {/* Overall progress */}
      {courses.length > 0 && (
        <div className="card">
          <h3>Overall progress</h3>
          <ProgressBar pct={overallPct} />
          <p className="muted" style={{ marginTop: 8 }}>
            {completedCount} of {courses.length} courses complete · {Math.round(overallPct)}% overall
          </p>
        </div>
      )}

      <div className="dash-grid">
        {/* Left column */}
        <div className="dash-col">
          {/* Assessment */}
          <div className="card">
            <h3>Assessment</h3>
            <p className="section-label">Summary</p>
            <p className="muted">{learnData.assessment_summary || '—'}</p>
            <p className="section-label" style={{ marginTop: 12 }}>Detected skills</p>
            <TagList tags={learnData.detected_skills} emptyText="None detected" />
            <p className="section-label" style={{ marginTop: 12 }}>Skill gaps</p>
            <TagList tags={learnData.skill_gaps?.slice(0, 8)} emptyText="None identified" />
          </div>

          {/* Skill gap analysis */}
          <div className="card">
            <h3>Skill gap analysis</h3>
            <p className="section-label">Priority skills to develop</p>
            <TagList tags={learnData.priority_skills} emptyText="None" />
            {learnData.gap_explanation && (
              <>
                <p className="section-label" style={{ marginTop: 12 }}>Explanation</p>
                <p className="muted">{learnData.gap_explanation}</p>
              </>
            )}
          </div>

          {/* Resources */}
          {learnData.initial_resources?.length > 0 && (
            <div className="card">
              <h3>Recommended resources</h3>
              <p className="muted" style={{ marginBottom: 12 }}>For your first course topic</p>
              <div className="resource-list">
                {learnData.initial_resources.map((r, i) => (
                  <ResourceCard key={i} resource={r} />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="dash-col">
          {/* Courses */}
          <div className="card">
            <h3>Your learning roadmap</h3>
            {courses.length === 0 ? (
              <p className="muted">No courses generated — try again with a more specific goal.</p>
            ) : (
              <div className="course-list">
                {courses
                  .slice()
                  .sort((a, b) => a.order_index - b.order_index)
                  .map(c => (
                    <CourseCard
                      key={c.id}
                      course={c}
                      progress={progressMap[c.id]}
                      saving={savingId === c.id}
                      onProgressUpdate={handleProgressUpdate}
                    />
                  ))}
              </div>
            )}
          </div>

          {/* AI Adaptation */}
          <div className="card">
            <h3>AI adaptation</h3>
            <p className="muted" style={{ marginBottom: 14 }}>
              Update your course progress above, then ask IBM Granite to analyse
              your progress and recommend adjustments to your roadmap.
            </p>
            <ErrorBanner message={adaptError} onDismiss={() => setAdaptError('')} />
            {adapting
              ? <Spinner label="Granite is analysing your progress…" />
              : (
                <button className="btn-primary" onClick={handleAdapt}>
                  ✦ Analyse &amp; adapt roadmap
                </button>
              )
            }
            {adaptation && (
              <div className="adaptation-result">
                <p className="section-label">Adaptation summary</p>
                <p className="muted">{adaptation.adaptation_summary}</p>
                {adaptation.recommendations?.length > 0 && (
                  <>
                    <p className="section-label" style={{ marginTop: 12 }}>Recommendations</p>
                    <ul className="rec-list">
                      {adaptation.recommendations.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </>
                )}
                <p style={{ marginTop: 10 }}>
                  <Badge type={adaptation.should_adapt ? 'warn' : 'ok'}>
                    {adaptation.should_adapt ? 'Roadmap adjustment applied' : 'On track — no changes needed'}
                  </Badge>
                </p>
                {adaptation.adapted_roadmap && (
                  <p className="muted" style={{ marginTop: 8, fontSize: '0.82rem' }}>
                    ✓ Roadmap updated · status: <strong>{adaptation.adapted_roadmap.status}</strong>
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── App shell ────────────────────────────────────────────────────────────────

const STEP = { PROFILE: 'profile', GOAL: 'goal', DASHBOARD: 'dashboard' }

export default function App() {
  const [step, setStep]           = useState(STEP.PROFILE)
  const [health, setHealth]       = useState(null)
  const [healthError, setHealthError] = useState(false)
  const [student, setStudent]     = useState(null)
  const [learnData, setLearnData] = useState(null)

  useEffect(() => {
    get('/health')
      .then(setHealth)
      .catch(() => setHealthError(true))
  }, [])

  const handleStudentCreated = useCallback(s => {
    setStudent(s)
    setStep(STEP.GOAL)
  }, [])

  const handleLearned = useCallback(data => {
    setLearnData(data)
    setStep(STEP.DASHBOARD)
  }, [])

  const handleReset = useCallback(() => {
    setStudent(null)
    setLearnData(null)
    setStep(STEP.PROFILE)
  }, [])

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div>
            <h1>🎓 LearnMate AI</h1>
            <p className="tagline">Agentic Personalised Learning — IBM Granite</p>
          </div>
          <div className="header-status">
            {healthError && <Badge type="error">Backend offline</Badge>}
            {health && (
              <>
                <Badge type="ok">Backend online</Badge>
                <Badge type={health.granite_configured ? 'granite' : 'warn'}>
                  {health.granite_configured ? '✦ Granite ready' : 'Granite unconfigured'}
                </Badge>
              </>
            )}
          </div>
        </div>

        {/* Step indicator */}
        <div className="steps">
          {[
            { id: STEP.PROFILE,   label: 'Profile' },
            { id: STEP.GOAL,      label: 'Goal' },
            { id: STEP.DASHBOARD, label: 'Dashboard' },
          ].map((s, i) => {
            const order = [STEP.PROFILE, STEP.GOAL, STEP.DASHBOARD]
            const active = s.id === step
            const done   = order.indexOf(s.id) < order.indexOf(step)
            return (
              <div key={s.id} className={`step ${active ? 'active' : ''} ${done ? 'done' : ''}`}>
                <div className="step-dot">{done ? '✓' : i + 1}</div>
                <span>{s.label}</span>
              </div>
            )
          })}
        </div>
      </header>

      <main className="main">
        {step === STEP.PROFILE && (
          <ProfileForm onCreated={handleStudentCreated} />
        )}
        {step === STEP.GOAL && student && (
          <GoalForm
            student={student}
            onLearned={handleLearned}
            onBack={() => setStep(STEP.PROFILE)}
          />
        )}
        {step === STEP.DASHBOARD && student && learnData && (
          <Dashboard
            student={student}
            learnData={learnData}
            onReset={handleReset}
          />
        )}
      </main>

      <footer className="footer">
        IBM SkillsBuild / AICTE Problem Statement #12 · IBM Granite · watsonx.ai
      </footer>
    </div>
  )
}
