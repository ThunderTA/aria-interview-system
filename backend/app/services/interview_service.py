"""Orchestrates a live interview session.

Ties together the three engines so the router stays thin:
  llm_judge   -> generates questions, scores answers
  rl_engine   -> picks the next question's difficulty from recent scores
  MongoDB     -> stores the session document and the shared Q-table

The Q-table is shared across users rather than stored per-user. Adaptation to
an individual happens through the RL *state* (their recent scores), while the
table itself learns the general policy ("high band at level 3 -> go harder").
A shared table reaches useful values after a handful of sessions; per-user
tables would each see too few samples to ever learn anything.
"""

import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services import llm_judge, rl_engine

logger = logging.getLogger(__name__)

QUESTIONS_PER_SESSION = 5
Q_TABLE_ID = "shared_policy"

# A session ending with fewer answered questions than this is too thin to be
# a meaningful data point — it gets marked discarded instead of completed, so
# it never appears in history or counts toward the average score.
MIN_ANSWERED_FOR_HISTORY = 2

# Where a session starts, by the seniority inferred from the resume.
STARTING_DIFFICULTY = {"intern": 2, "junior": 2, "mid": 3, "senior": 4}
DEFAULT_DIFFICULTY = 3


async def load_q_table(db: AsyncIOMotorDatabase) -> dict:
    doc = await db.rl_policy.find_one({"_id": Q_TABLE_ID})
    return (doc or {}).get("q_table", {})


async def save_q_table(db: AsyncIOMotorDatabase, q_table: dict) -> None:
    await db.rl_policy.update_one(
        {"_id": Q_TABLE_ID},
        {"$set": {"q_table": q_table, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def get_candidate_context(db: AsyncIOMotorDatabase, user_id: str) -> tuple[list[str], int]:
    """Resume-derived skills and starting difficulty. Falls back cleanly if no resume."""
    resume = await db.resumes.find_one({"user_id": user_id})
    if not resume:
        return [], DEFAULT_DIFFICULTY

    skills = [s["name"] for s in resume.get("parsed_skills", [])]
    difficulty = STARTING_DIFFICULTY.get(resume.get("inferred_level"), DEFAULT_DIFFICULTY)
    return skills, difficulty


def answered_scores(questions: list[dict]) -> list[float]:
    """Content scores of the questions answered so far, in order."""
    return [q["content_score"] for q in questions if q.get("content_score") is not None]


def performance_scores(questions: list[dict]) -> list[float]:
    """The scores the difficulty policy reacts to.

    The rubric score where it exists; otherwise, in a conversational interview
    whose last answer is still being scored, the interviewer's in-the-moment
    impression of it — so the next question doesn't have to wait for the rubric.
    """
    return [
        q["content_score"] if q.get("content_score") is not None else q["provisional_score"]
        for q in questions
        if q.get("content_score") is not None or q.get("provisional_score") is not None
    ]


async def build_next_question(
    db: AsyncIOMotorDatabase,
    session: dict,
    user_id: str,
    starting_difficulty: int | None = None,
) -> dict:
    """Generate the next question at the difficulty the RL policy recommends.

    `starting_difficulty` only matters for the first question of a session —
    it's the candidate's explicit choice from Setup, overriding the
    resume-derived default. Every question after that is chosen by the RL
    policy regardless, since the whole point of adapting is that a starting
    guess (candidate's or the resume's) stops being the reference point once
    there's real performance to react to.
    """
    questions = session.get("questions", [])
    skills, resume_difficulty = await get_candidate_context(db, user_id)

    if questions:
        q_table = await load_q_table(db)
        difficulty = rl_engine.select_next_difficulty(
            performance_scores(questions), questions[-1]["difficulty_level"], q_table
        )
    else:
        difficulty = starting_difficulty if starting_difficulty is not None else resume_difficulty

    generated = await llm_judge.generate_question(
        role=session["role"],
        difficulty_level=difficulty,
        skills=skills,
        asked_questions=[q["text"] for q in questions],
    )

    return {
        "question_id": f"q{len(questions) + 1}",
        "text": generated["question"],
        "topic": generated["topic"],
        "difficulty_level": difficulty,
        "order_index": len(questions),
    }


async def score_and_advance(
    db: AsyncIOMotorDatabase,
    session: dict,
    transcript: str,
    delivery: dict | None = None,
    visual: dict | None = None,
    *,
    index: int | None = None,
    follow_ups: list[tuple[str, str]] | None = None,
    background: bool = False,
) -> dict:
    """Score a question's answer and learn from the outcome.

    `index` defaults to the last question; a conversational interview passes
    it explicitly, since the next question may already have been asked by the
    time an earlier answer is scored. Returns the scored question dict. Does
    not persist — the caller decides how to write it.
    """
    questions = session["questions"]
    position = len(questions) - 1 if index is None else index
    current = questions[position]

    scored = await llm_judge.score_answer(
        question=current["text"],
        transcript=transcript,
        role=session["role"],
        follow_ups=follow_ups,
        background=background,
    )

    prior_scores = answered_scores(questions[:position])
    difficulty = current["difficulty_level"]
    # The action the policy took was the step from the previous question's
    # difficulty to this one's. The first question follows no action.
    previous_difficulty = questions[position - 1]["difficulty_level"] if position >= 1 else None

    current.update(
        {
            "transcript": transcript,
            "content_score": scored["content_score"],
            "rubric": {k: scored[k] for k in ("correctness", "depth", "relevance", "clarity")},
            "feedback_text": scored["feedback"],
            "answered_at": datetime.now(timezone.utc),
        }
    )
    # Present only for spoken answers; typed ones have no delivery to measure.
    if delivery:
        current.update(
            {
                "wpm": delivery["wpm"],
                "pause_count": delivery["pause_count"],
                "filler_count": delivery["filler_count"],
                "delivery_score": delivery["delivery_score"],
                "delivery_breakdown": delivery["delivery_breakdown"],
                "delivery_note": delivery["note"],
            }
        )
    # Present only when the camera was on and a face was actually visible.
    if visual:
        current.update(
            {
                "gaze_score": visual["gaze_score"],
                "expression_score": visual["expression_score"],
                "posture_score": visual["posture_score"],
                "face_presence": visual["face_presence"],
                "visual_note": visual["note"],
            }
        )

    if previous_difficulty is not None:
        await _learn_from_turn(
            db, prior_scores, previous_difficulty, difficulty, scored["content_score"]
        )
    return current


async def _learn_from_turn(
    db: AsyncIOMotorDatabase,
    prior_scores: list[float],
    previous_difficulty: int,
    difficulty: int,
    score: float,
) -> None:
    """Apply one Q-learning update for the turn that just completed.

    The transition being learned is: from the state the policy saw when it
    chose this question (scores before it, previous difficulty), it took the
    action `difficulty - previous_difficulty` and earned a reward based on how
    well the candidate then scored.
    """
    try:
        prior_before_action = prior_scores[:-1] if prior_scores else []
        state = rl_engine.state_key(prior_before_action, previous_difficulty)
        action = rl_engine.clamp_difficulty(difficulty) - rl_engine.clamp_difficulty(
            previous_difficulty
        )
        next_state = rl_engine.state_key(prior_scores + [score], difficulty)
        reward = rl_engine.compute_reward(score, difficulty)

        q_table = await load_q_table(db)
        rl_engine.update_q_table(q_table, state, action, reward, next_state)
        await save_q_table(db, q_table)
    except Exception:
        # Learning is best-effort: a failed policy update must never break the
        # interview the candidate is currently sitting.
        logger.exception("Q-table update failed; continuing without learning from this turn")


def compute_aggregates(questions: list[dict]) -> dict:
    """Session-level averages across the answered questions."""
    scores = answered_scores(questions)
    if not scores:
        return {
            "overall_score": None,
            "content_score_avg": None,
            "delivery_score_avg": None,
            "visual_score_avg": None,
        }

    content_avg = round(sum(scores) / len(scores), 1)
    delivery = [q["delivery_score"] for q in questions if q.get("delivery_score") is not None]

    # Visual is the mean of gaze, expression and posture across the answers
    # where the camera was actually on.
    visual_per_question = [
        (q["gaze_score"] + q["expression_score"] + q["posture_score"]) / 3
        for q in questions
        if q.get("gaze_score") is not None
        and q.get("expression_score") is not None
        and q.get("posture_score") is not None
    ]

    delivery_avg = round(sum(delivery) / len(delivery), 1) if delivery else None
    visual_avg = (
        round(sum(visual_per_question) / len(visual_per_question), 1)
        if visual_per_question
        else None
    )

    # Dimensions the candidate didn't use (typed answers, camera off) are left
    # out of the overall rather than counted as zero, which would misrepresent
    # them as having performed badly.
    present = [v for v in (content_avg, delivery_avg, visual_avg) if v is not None]
    return {
        "overall_score": round(sum(present) / len(present), 1),
        "content_score_avg": content_avg,
        "delivery_score_avg": delivery_avg,
        "visual_score_avg": visual_avg,
    }


async def summarise(role: str, questions: list[dict]) -> dict[str, list[str]]:
    """Session-level strengths and improvements, generated once when it ends.

    Best-effort: a summary failure must not stop a session being finalised, so
    the report simply shows no themes rather than erroring.
    """
    answered = [q for q in questions if q.get("content_score") is not None]
    if not answered:
        return {"strengths": [], "improvements": []}

    try:
        return await llm_judge.summarise_session(role, answered)
    except Exception:
        logger.exception("Session summary failed; returning no themes")
        return {"strengths": [], "improvements": []}
