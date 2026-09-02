# ARIA — Adaptive Real-Time Interview Assessment System

ARIA is an AI-based platform that lets students and job seekers practice
mock interviews without needing a human interviewer. It conducts
role-specific interviews using an LLM, adapts question difficulty in
real time based on performance (via a reinforcement-learning engine),
transcribes spoken answers (Whisper), scores both *what* was said (an
LLM-as-judge evaluates correctness/depth/relevance) and *how* it was
said (speaking speed, pauses, filler words, eye contact, expression,
posture), and tracks a candidate's progress across sessions.

Built for the BE Major Project, Semester VII, Group 10, Department of
CSE-Data Science, APSIT (SDG 4 — Quality Education).

For the full feature list, MVP/stretch split, database schema, and API
design, see [`docs/architecture.md`](docs/architecture.md).

## Tech Stack

- **Frontend**: React (Vite), React Router, Axios
- **Backend**: Python, FastAPI
- **Database**: MongoDB
- **AI / LLM**: Large Language Models, Hugging Face Transformers
- **NLP**: Sentence Transformers
- **Speech**: Whisper (ASR), Librosa (delivery metrics)
- **ML**: Scikit-learn, PyTorch (RL difficulty engine)
- **CV**: OpenCV, MediaPipe (gaze / expression / posture)
- **Auth**: JWT

## Project Structure

```
.
├── backend/            # FastAPI application
│   ├── app/
│   │   ├── main.py         # app entrypoint, CORS, router registration
│   │   ├── core/            # config, JWT/password security, auth dependency
│   │   ├── db/               # MongoDB (Motor) connection
│   │   ├── models/          # Pydantic schemas (user, resume, session)
│   │   ├── routers/         # REST + WebSocket endpoints
│   │   └── services/        # ASR / LLM-judge / RL engine / CV analysis
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/            # React (Vite) application
│   ├── src/
│   │   ├── api/              # HTTP client + auth API calls
│   │   ├── components/      # shared/reusable components (BrandPanel, FormField, Logo, ProtectedRoute)
│   │   ├── pages/            # route-level pages + their scoped CSS
│   │   ├── styles/           # design tokens (colors/type/spacing) + global styles
│   │   └── router.jsx
│   └── .env.example
└── docs/
    └── architecture.md   # feature list, schema, API design, diagrams
```

## Prerequisites

- Python 3.12+ (developed against 3.13)
- Node.js 20+
- MongoDB running locally (e.g. via MongoDB Compass / Community Server),
  reachable at `mongodb://localhost:27017` by default

## Setup

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` if your MongoDB isn't on the default local port, and
set a real `JWT_SECRET` (any long random string) before deploying anywhere
beyond your own machine.

Run the API:

```bash
uvicorn app.main:app --reload
```

The API is now at `http://localhost:8000`. Check `GET /health` returns
`{"status": "ok"}`, and interactive docs are at `/docs`.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open the URL Vite prints (default `http://localhost:5173`). `VITE_API_BASE_URL`
in `frontend/.env` must match wherever the backend is actually running.

> **Ports already in use?** If 8000 or 5173 are taken by something else on
> your machine, FastAPI/Vite will either fail to bind or pick a fallback
> port. Pass `--port <n>` to `uvicorn`, and update `CORS_ORIGINS` in
> `backend/.env` plus `VITE_API_BASE_URL` in `frontend/.env` to match
> whatever ports you end up using.

### Verifying it works end-to-end

1. With both servers running, open the frontend — you should land on
   `/login`.
2. Click "Sign up", create an account. You should be redirected to
   `/dashboard` and see your name/email (confirms frontend → backend →
   MongoDB all work together).
3. Open MongoDB Compass, connect to `localhost:27017`, and check the
   `aria` database's `users` collection — your new user should be there.
4. Click "Log out", then try visiting `/dashboard` directly — you should
   be bounced back to `/login` (confirms the route guard works).

## Design System

The frontend uses a deliberate dark, tech-forward visual identity (not the
default Tailwind-indigo look): design tokens live in
`frontend/src/styles/tokens.css` — an amber/teal accent pair, a
Space Grotesk (headings) + Inter (body) font pairing self-hosted via
`@fontsource` (no external font CDN, so demos work offline), and an 8px
spacing scale. The dashboard uses a bento-grid layout
(`frontend/src/pages/Dashboard.css`); auth pages use a split-screen layout
with an animated brand panel (`frontend/src/components/BrandPanel.jsx`).
Extend these tokens rather than hardcoding new colors when building further
pages, to keep the product visually consistent.

## Current Status

**Working end-to-end:** the auth vertical slice (signup, login, JWT
refresh, `/users/me`) across frontend, backend, and MongoDB.

**All 6 UI screens exist:** Login, Signup, Dashboard (bento grid), Setup
(resume upload + role selection), Interview, and Report.

**Not built yet:** the AI backend. `POST /resume/upload`, the session
endpoints, and the WebSocket interview loop are scaffolded with correct
route signatures and Pydantic models but return `501 Not Implemented`, each
with a `TODO` pointing at the relevant module in `backend/app/services/`
(`asr.py`, `llm_judge.py`, `rl_engine.py`, `cv_analysis.py`).

Because of that, the Interview and Report screens run in a clearly-labelled
**Preview mode** — they show the real layout and interactions, but nothing
is recorded, transcribed, or scored yet, and no fake scores are displayed.
Setup's resume upload calls the real endpoint and handles the expected
`501` with a plain explanatory notice. Next build steps per the project
timeline: STT integration, LLM feedback engine, RL difficulty engine, CV
analysis, session history (see the Gantt chart in the project proposal).

## Deployment

The backend includes a `Dockerfile` (multi-stage not needed — it's a
single Python service) for deploying to a platform like Railway. The
frontend is a static Vite build, deployable to Vercel/Netlify without
Docker. Point `VITE_API_BASE_URL` at the deployed backend URL and
`CORS_ORIGINS` (backend) at the deployed frontend URL before going live.
