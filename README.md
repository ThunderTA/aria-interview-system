# ARIA - Adaptive Real-Time Interview Assessment System

ARIA is an AI-based platform that lets students and job seekers practice
mock interviews without needing a human interviewer. It conducts
role-specific interviews using an LLM, adapts question difficulty in
real time based on performance (via a reinforcement-learning engine),
transcribes spoken answers (Whisper), scores both *what* was said (an
LLM-as-judge evaluates correctness/depth/relevance) and *how* it was
said (speaking speed, pauses, filler words, eye contact, expression,
posture), and tracks a candidate's progress across sessions.

Built for the BE Major Project, Semester VII, Group 10, Department of
CSE-Data Science, APSIT (SDG 4 - Quality Education).

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
- [Ollama](https://ollama.com) for the local LLM - `brew install ollama`,
  then `ollama serve` and `ollama pull qwen2.5:7b` (~4.7 GB, one time)

Whisper needs no separate install: `faster-whisper` comes from
`requirements.txt` and bundles its own media decoding, so there is no system
ffmpeg dependency. The speech model downloads itself on first use, and the
interviewer's voice (Kokoro, ~350 MB) and the face-verification models
(~39 MB) download themselves the first time the backend starts.

Everything runs on your machine - no API keys, no per-interview cost, and
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

1. With both servers running, open the frontend - you should land on
   `/login`.
2. Click "Sign up", create an account. You should be redirected to
   `/dashboard` and see your name/email (confirms frontend → backend →
   MongoDB all work together).
3. Open MongoDB Compass, connect to `localhost:27017`, and check the
   `aria` database's `users` collection - your new user should be there.
4. Click "Log out", then try visiting `/dashboard` directly - you should
   be bounced back to `/login` (confirms the route guard works).

## Design System

A light, formal visual identity (not the default Tailwind-indigo look):
design tokens live in `frontend/src/styles/tokens.css` - an amber/teal
accent pair, a Space Grotesk (headings) + Inter (body) font pairing
self-hosted via `@fontsource` (no external font CDN, so demos work
offline), and an 8px spacing scale. The dashboard uses a bento-grid layout
(`frontend/src/pages/Dashboard.css`); auth pages use a split-screen layout
with an animated, touchable brand panel (`frontend/src/components/BrandPanel.jsx`).

The raw `--accent`/`--signal` brand colors are vivid and fail text contrast
against the light background (~1.8:1) - they're for fills only (buttons,
gradients, translucent badge backgrounds, icon-chip backgrounds). Anything
rendering as foreground text or a small icon uses the darkened
`--accent-text`/`--signal-text`/`--danger-text` variants instead, each
verified >=4.5:1 against both `--bg` and `--surface`. Large display numbers
(2rem+, e.g. dashboard stats, report scores) use the `.gradient-text`
utility with `--gradient-pop` - a deepened version of the button gradient,
since the button gradient's own stops don't clear even the 3:1 large-text
floor. Extend these tokens rather than hardcoding new colors when building
further pages, and re-check contrast against `--bg`/`--surface` (not just
eyeballing it) before using a brand color as text.

## Current Status

**Working end-to-end:**

- Auth vertical slice (signup, login, JWT refresh, `/users/me`) across
  frontend, backend, and MongoDB.
- **Resume parsing** - `POST /resume/upload` accepts a PDF/`.docx`, extracts
  the text, matches it against a skill taxonomy, and infers the candidate's
  role (SDE/HR) and seniority. Results are stored in the `resumes`
  collection (one current resume per user) and shown on the Setup screen,
  which pre-selects the inferred role. `GET`/`PATCH /resume` let the
  candidate read back and correct what was inferred.

**A public landing page plus all 6 authenticated screens:** Landing, Login,
Signup, Dashboard (bento grid), Setup (resume upload - required, since
questions are grounded in it - + role selection), Interview, and Report
(with a per-question speaking-pace grid alongside the breakdown).

- **Spoken answers** - the candidate speaks; the browser records, the backend
  transcribes locally with faster-whisper, and the same scoring path runs.
  Audio is transcribed then discarded; only the transcript and derived
  numbers are stored.
- **Delivery analysis** - speaking pace, long pauses and filler words, all
  derived from Whisper's word-level timings, combined into a delivery score
  (`backend/app/services/speech_metrics.py`).
- **Adaptive questioning** - an LLM generates role-specific questions and
  grades answers against a rubric; a tabular Q-learning policy moves the
  difficulty up or down based on recent scores.

- **Visual analysis** - with the camera on, frames are sampled at ~1 fps while
  the candidate answers and scored by MediaPipe for eye contact, expression
  and head posture (`backend/app/services/cv_analysis.py`). Frames are
  analysed and discarded; no video is stored or uploaded anywhere off the
  machine.

- **Session recording threshold** - a session only counts toward history
  and the average-score calculation once at least
  `MIN_ANSWERED_FOR_HISTORY` (2) questions have been answered.
  `POST /sessions/{id}/end` is the single exit point regardless of how a
  session ends - finishing normally, clicking finish early, or confirming
  a leave - and it decides completed-vs-discarded itself based on that
  count, so no caller has to. A discarded session keeps no scores and
  never appears in the dashboard's history or trend.

- **Leave confirmation** - navigating away from an in-progress interview
  (the logo, the Dashboard link, or Log out, all via `AppHeader`'s
  `onNavigateAttempt`) shows a confirmation dialog naming the actual
  consequence - "saves to history" above the threshold, "won't be saved"
  below it - rather than a generic warning. A `beforeunload` listener is
  a backstop for tab close/refresh, which in-app navigation guarding can't
  intercept.

- **Conversational interview mode** - chosen in Setup alongside the classic
  one-question-at-a-time flow. ARIA greets the candidate by name, asks them
  to introduce themselves, then works through five adaptive questions as a
  spoken back-and-forth: after each answer it follows up (at most twice),
  clarifies when asked, or moves on, and it closes by inviting the
  candidate's own questions. The interviewer speaks with Kokoro, a local
  neural voice - one of six, picked in Setup and previewed with a click - sentence by sentence (the browser's voice is the fallback),
  and a turn ends hands-free after about three seconds of silence or with a
  Done button. Each question's whole exchange is scored as one answer in the
  background, so the conversation never waits on the rubric; scores appear
  on screen as they land, and until then the next question's difficulty uses
  the interviewer's quick estimate. A priority gate in `llm_client.py` puts
  the interviewer's reply ahead of queued scoring, since Ollama generates one
  response at a time. See `conversation_service.py`, `interviewer.py` and
  `tts.py`.

- **Eye tracking and attention** - the camera says where the candidate is
  looking, not just whether a face is present. Head orientation (turn, nod
  and tilt, each axis checked against mirrored and rotated frames rather than
  assumed) is combined with eye direction from the landmarker's eye-look
  blendshapes, so a head turned aside with the eyes back on the lens counts
  as eye contact - which the old head-only measure scored as none. Each frame
  lands in one state: looking at the camera, down, up, away to the left or
  right, turned away, eyes closed, or out of frame. A badge on the camera
  preview names the current state every few seconds, the report breaks the
  interview down by share of time with a per-question line, and a *sustained*
  spell away (default: four checks in a row) is recorded as an episode. It is
  deliberately kept out of the identity verdict: looking at a second screen
  says nothing about who is sitting there. See `cv_analysis.py` and
  `attention_service.py`; thresholds live beside the geometry they describe.

- **Candidate identity verification** - confirms the person interviewing is
  the person on the resume. A profile photo in the resume (PDF or `.docx`) is
  detected and turned into a face embedding; with no usable photo, the
  candidate verifies once on camera instead. Either way the first question
  stays locked until that start check passes, and a frame is re-checked every
  15 seconds after. Single bad frames only move counters: several mismatches
  or several multi-person frames in a row raise a quiet warning and an
  integrity event, and the report shows the method, every count and an
  overall verdict. Uses OpenCV's YuNet detector and SFace recognizer (cosine
  similarity on 128-d embeddings) - no new pip dependency. Embeddings are
  Fernet-encrypted in `identity_references` with a TTL index, never returned
  by the API or logged; the session's copy is deleted when it ends, and
  frames are never stored. Thresholds are in `backend/app/core/config.py`
  (see `IDENTITY_*` in `.env.example`); logic is in
  `backend/app/services/face_identity.py` and `identity_service.py`.

- **Downloadable report** - `GET /sessions/{id}/report/pdf` renders the same
  report as a PDF on the fly (fpdf2, built-in fonts, nothing stored): scores,
  themes, identity verdict, attention breakdown, and every question with its
  rubric, notes, feedback and conversation transcript. The report screen has
  a "Download PDF" button.

**Not built yet:** the WebSocket streaming loop for live transcript display
as the candidate speaks, and PDF report export.

Dimensions that weren't measured (delivery on a typed answer, visual with the
camera off) are left out of the overall score rather than counted as zero,
and the report says which were skipped.

The resume parser is deliberately rule-based (see
`backend/app/data/skill_taxonomy.py` and
`backend/app/services/resume_parser.py`): it needs no API key, runs
instantly, and is easy to extend - add a skill by adding one line to the
taxonomy. It can be swapped for an LLM-backed parser later without touching
the router, since the parsing functions are pure.

## Deployment

The backend includes a `Dockerfile` (multi-stage not needed - it's a
single Python service) for deploying to a platform like Railway. The
frontend is a static Vite build, deployable to Vercel/Netlify without
Docker. Point `VITE_API_BASE_URL` at the deployed backend URL and
`CORS_ORIGINS` (backend) at the deployed frontend URL before going live.
