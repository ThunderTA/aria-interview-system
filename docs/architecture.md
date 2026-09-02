# ARIA — Architecture & Design Decisions

This document captures the product and technical decisions made during
project planning, before implementation began. It exists so the whole team
has a shared reference, not just whoever was in the planning conversation.

## Feature List

**Onboarding & Personalization**
- JWT auth (signup/login)
- Resume upload → parsed to (a) infer default role & seniority, (b) extract
  skills/projects used to personalize generated questions
- Role selection: SDE or HR/Behavioral (resume sets a default; user can
  override)

**Adaptive Interview Engine**
- LLM generates role-specific questions
- Difficulty adjusts turn-by-turn via a **tabular Q-learning / contextual
  bandit** (not deep RL — chosen for feasibility: fast to train, easy to
  explain in a viva, doesn't need a large training corpus). State: last 2-3
  answer scores + current difficulty tier. Action: `{easier, same, harder}`.
  Reward: weighted combination of content + delivery score.

**Multimodal Assessment (per answer)**
- **ASR**: Whisper transcribes spoken answers, driven by VAD-based
  utterance segmentation over the live WebSocket audio stream (see
  "Real-Time Interview Loop" below) — not full continuous streaming
  transcription.
- **Content evaluation**: LLM-as-judge — one call scores
  correctness/depth/relevance/clarity **and** produces the feedback text,
  since both are needed anyway.
- **Speech delivery**: WPM, pause count/duration, filler-word count
  (Librosa).
- **Visual (CV)**: gaze/eye-contact, facial expression, posture — via
  OpenCV/MediaPipe, sampled at ~2-5 fps from streamed video frames (not
  full frame-rate).

**Feedback & Skill-Gap Report**
- Aggregated score breakdown (content vs. delivery vs. visual)
- Strengths/weaknesses + personalized recommendations
- PDF export (jsPDF)

**Progress Tracking**
- Every session stored in MongoDB
- Dashboard showing score trends across sessions

## MVP vs. Stretch

Stretch items are still in scope for the final deliverable — this split is
about *build order* (matches the project Gantt chart), not about cutting
anything.

**MVP**: auth · resume upload+parsing · role selection (SDE/HR) ·
Q-learning/bandit adaptive questioning · Whisper transcription · LLM-judge
scoring+feedback · speech metrics (WPM/pauses/fillers) · real-time
eye-contact/gaze tracking · on-screen session report · session history +
progress dashboard · WebSocket-based real-time interview loop.

**Stretch** (built after MVP is demoable): facial expression/emotion
detection · posture/fidgeting analysis · PDF report export · additional
roles beyond SDE/HR · deep-RL upgrade · deeper resume-grounded question
personalization (referencing specific past projects).

## Why MongoDB (not the originally-proposed PostgreSQL)

A session is fundamentally a nested object: one interview with an ordered
list of questions, each carrying a transcript + several score fields. It's
almost always read/written as **one whole session**, not joined across
tables — a natural fit for an embedded-document model. Mongo also avoids
migrations while score fields are still being iterated on.

The one weak spot: cross-session analytics (e.g. score trend over the last
N sessions) is more natural in SQL than in Mongo's aggregation pipeline —
not hard, just less ergonomic. Worth knowing if the progress-dashboard query
gets gnarly later.

> Note: the originally submitted project proposal names PostgreSQL in the
> tech stack. This was a deliberate deviation made during planning — update
> the tech stack section of the report to reflect MongoDB.

## Database Schema (MongoDB, database name: `aria`)

- **users**: `{ _id, email (unique index), password_hash, name, created_at }`
- **resumes**: `{ _id, user_id, raw_text, parsed_skills: [...], inferred_role, inferred_level, uploaded_at }`
- **sessions** (core collection — questions/answers embedded, not separate):
```json
{
  "_id": "...",
  "user_id": "...",
  "role": "SDE | HR",
  "status": "in_progress | completed | discarded",
  "started_at": "...",
  "ended_at": "...",
  "overall_score": 0,
  "content_score_avg": 0,
  "delivery_score_avg": 0,
  "visual_score_avg": 0,
  "questions": [
    {
      "question_id": "...",
      "text": "...",
      "difficulty_level": 1,
      "order_index": 0,
      "transcript": "...",
      "wpm": 0, "pause_count": 0, "filler_count": 0,
      "content_score": 0, "delivery_score": 0,
      "gaze_score": 0, "expression_score": 0, "posture_score": 0,
      "feedback_text": "..."
    }
  ]
}
```

Indexes: `users.email` (unique), `sessions.user_id + started_at` (history
list + progress dashboard queries).

Raw audio/video are **not stored** — only derived metrics and the text
transcript persist, matching the proposal's safety/security claims.

## API Design

**Auth & User**
- `POST /auth/signup`, `POST /auth/login`, `POST /auth/refresh`
- `GET /users/me`, `PATCH /users/me`

**Resume**
- `POST /resume/upload`
- `GET /resume`, `PATCH /resume`

**Session Lifecycle**
- `POST /sessions`, `GET /sessions`, `GET /sessions/{id}`,
  `DELETE /sessions/{id}`, `POST /sessions/{id}/end`

**Real-Time Interview Loop**
- `WS /sessions/{id}/stream` — one WebSocket per session; client streams
  audio chunks + sampled video frames continuously; server pushes back
  partial transcript, live gaze/attention signal, and the next question
  when ready. This is core to the MVP (real-time is literally in the
  project name), not a stretch upgrade over a REST-per-answer flow.

**Reporting & Progress**
- `GET /sessions/{id}/report`, `GET /sessions/{id}/report/pdf`
- `GET /users/me/progress`

**Utility**
- `GET /health`

## System Diagram

```
React Frontend (webcam + mic capture, UI)
        │  REST + WebSocket
        ▼
FastAPI Backend (orchestration, auth, business logic)
        │
   ┌────┼─────────────┬──────────────┬───────────────┐
   ▼    ▼             ▼              ▼               ▼
Whisper  LLM Service  RL Difficulty  Speech/CV        MongoDB
(ASR)    (Qgen +      Engine         Analysis         (users, sessions,
         Judge)       (Q-learning)   (Librosa +        resumes)
                                      MediaPipe)
```

Heavy ML work happens in dedicated services behind the FastAPI backend, not
in the browser — the frontend stays thin, and each ML piece (ASR, LLM
judge, RL engine, CV analysis) is independently testable. See
`backend/app/services/` for where each one plugs in.
