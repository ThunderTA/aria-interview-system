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
- [Ollama](https://ollama.com) for the local LLM — `brew install ollama`,
  then `ollama serve` and `ollama pull qwen2.5:7b` (~4.7 GB, one time)

Whisper needs no separate install: `faster-whisper` comes from
`requirements.txt` and bundles its own media decoding, so there is no system
ffmpeg dependency. The speech model downloads itself on first use.

Everything runs on your machine — no API keys, no per-interview cost, and
the app works with no internet connection once the models are pulled.

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

**Working end-to-end:**

- Auth vertical slice (signup, login, JWT refresh, `/users/me`) across
  frontend, backend, and MongoDB.
- **Resume parsing** — `POST /resume/upload` accepts a PDF/`.docx`, extracts
  the text, matches it against a skill taxonomy, and infers the candidate's
  role (SDE/HR) and seniority. Results are stored in the `resumes`
  collection (one current resume per user) and shown on the Setup screen,
  which pre-selects the inferred role. `GET`/`PATCH /resume` let the
  candidate read back and correct what was inferred.

**All 6 UI screens exist:** Login, Signup, Dashboard (bento grid), Setup
(resume upload + role selection), Interview, and Report.

- **Spoken answers** — the candidate speaks; the browser records, the backend
  transcribes locally with faster-whisper, and the same scoring path runs.
  Audio is transcribed then discarded; only the transcript and derived
  numbers are stored.
- **Delivery analysis** — speaking pace, long pauses and filler words, all
  derived from Whisper's word-level timings, combined into a delivery score
  (`backend/app/services/speech_metrics.py`).
- **Adaptive questioning** — an LLM generates role-specific questions and
  grades answers against a rubric; a tabular Q-learning policy moves the
  difficulty up or down based on recent scores.

- **Visual analysis** — with the camera on, frames are sampled at ~1 fps while
  the candidate answers and scored by MediaPipe for eye contact, expression
  and head posture (`backend/app/services/cv_analysis.py`). Frames are
  analysed and discarded; no video is stored or uploaded anywhere off the
  machine.

**Not built yet:** the WebSocket streaming loop for live transcript display
as the candidate speaks, and PDF report export.

Dimensions that weren't measured (delivery on a typed answer, visual with the
camera off) are left out of the overall score rather than counted as zero,
and the report says which were skipped.

The resume parser is deliberately rule-based (see
`backend/app/data/skill_taxonomy.py` and
`backend/app/services/resume_parser.py`): it needs no API key, runs
instantly, and is easy to extend — add a skill by adding one line to the
taxonomy. It can be swapped for an LLM-backed parser later without touching
the router, since the parsing functions are pure.

## Deployment

The backend includes a `Dockerfile` (multi-stage not needed — it's a
single Python service) for deploying to a platform like Railway. The
frontend is a static Vite build, deployable to Vercel/Netlify without
Docker. Point `VITE_API_BASE_URL` at the deployed backend URL and
`CORS_ORIGINS` (backend) at the deployed frontend URL before going live.
