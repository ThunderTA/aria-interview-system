"""Interview question generation and LLM-as-judge answer scoring.

Two responsibilities, both driven by the local LLM (see llm_client.py):

1. `generate_question` - produce the next question for a role at a given
   difficulty, optionally grounded in the candidate's resume skills.
2. `score_answer` - grade a transcribed answer against a fixed rubric and
   return both the numeric scores and the feedback text shown to the
   candidate. One call does both, since the feedback is needed anyway.

Difficulty is an integer 1-5; see rl_engine.py for how it gets chosen.
"""

from app.services.llm_client import chat_json

DIFFICULTY_LABELS = {
    1: "very easy warm-up",
    2: "easy",
    3: "moderate",
    4: "challenging",
    5: "very challenging, senior-level",
}

ROLE_BRIEFS = {
    "SDE": (
        "a software development engineer interview covering data structures, algorithms, "
        "system design, language fundamentals, databases, and practical engineering trade-offs"
    ),
    "DS": (
        "a data science interview covering statistics and probability, experiment design "
        "(A/B testing), SQL and data wrangling, core machine learning concepts, and how the "
        "candidate communicates analytical findings to a non-technical audience"
    ),
    "MLE": (
        "a machine learning engineering interview covering model deployment and serving, "
        "feature pipelines, MLOps practices, model monitoring, and the trade-offs between "
        "model performance and production system constraints"
    ),
    "QA": (
        "a QA and test engineering interview covering test case design, manual versus "
        "automated testing strategy, bug triage and reporting, regression testing, and how "
        "the candidate builds confidence that software is ready to ship"
    ),
    "PM": (
        "a product management interview covering prioritization frameworks, product sense, "
        "defining and moving metrics, stakeholder communication, and how the candidate scopes "
        "and ships a feature from problem to launch"
    ),
    "HR": (
        "an HR and behavioural interview covering motivation, teamwork, conflict handling, "
        "strengths and weaknesses, career goals, and the story behind the candidate's resume"
    ),
}

QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "topic": {"type": "string"},
    },
    "required": ["question", "topic"],
}

# Kept deliberately lean. Generation is output-token-bound on a local model
# (~0.27s/token on an M4), so every extra field is felt directly as latency by
# a candidate waiting mid-interview. Session-level strengths and improvements
# are produced once by summarise_session() instead of on every answer.
SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "correctness": {"type": "integer", "minimum": 0, "maximum": 10},
        "depth": {"type": "integer", "minimum": 0, "maximum": 10},
        "relevance": {"type": "integer", "minimum": 0, "maximum": 10},
        "clarity": {"type": "integer", "minimum": 0, "maximum": 10},
        "feedback": {"type": "string"},
    },
    "required": ["correctness", "depth", "relevance", "clarity", "feedback"],
}

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "strengths": {"type": "array", "items": {"type": "string"}},
        "improvements": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["strengths", "improvements"],
}

RUBRIC_WEIGHTS = {"correctness": 0.4, "depth": 0.25, "relevance": 0.2, "clarity": 0.15}


async def generate_question(
    role: str,
    difficulty_level: int,
    skills: list[str] | None = None,
    asked_questions: list[str] | None = None,
) -> dict:
    """Generate the next interview question. Returns {question, topic}."""
    brief = ROLE_BRIEFS.get(role, ROLE_BRIEFS["SDE"])
    label = DIFFICULTY_LABELS.get(difficulty_level, DIFFICULTY_LABELS[3])

    system_prompt = (
        "You are an experienced technical interviewer conducting "
        f"{brief}. You ask one focused question at a time. Questions must be "
        "answerable out loud in 60-90 seconds, with no code writing required. "
        "Never include the answer, hints, or commentary."
    )

    parts = [f"Ask one {label} interview question."]
    if skills:
        parts.append(
            "Ground it in the candidate's background where it fits naturally. "
            f"Their skills: {', '.join(skills[:15])}."
        )
    if asked_questions:
        already = "\n".join(f"- {q}" for q in asked_questions[-8:])
        parts.append(f"Do not repeat or closely paraphrase any of these:\n{already}")
    parts.append('Respond as JSON: {"question": "...", "topic": "short topic label"}')

    result = await chat_json(
        system_prompt, "\n\n".join(parts), QUESTION_SCHEMA, temperature=0.8, max_tokens=120
    )
    return {
        "question": result["question"].strip(),
        "topic": result["topic"].strip(),
    }


async def score_answer(
    question: str,
    transcript: str,
    role: str = "SDE",
    follow_ups: list[tuple[str, str]] | None = None,
    *,
    background: bool = False,
) -> dict:
    """Grade a spoken answer against the rubric.

    `follow_ups` are (interviewer question, candidate reply) pairs from a
    conversational interview. The whole exchange is graded as one answer, so a
    good follow-up reply can supply depth the first answer lacked.

    Returns the four rubric scores (0-10), a weighted `content_score` (0-100),
    and the feedback paragraph.
    """
    follow_ups = follow_ups or []
    if not transcript.strip() and not any(reply.strip() for _, reply in follow_ups):
        return _empty_answer_result()

    brief = ROLE_BRIEFS.get(role, ROLE_BRIEFS["SDE"])
    system_prompt = (
        f"You are grading a candidate's spoken answer in {brief}. "
        "The text is an automatic transcript of speech, so ignore punctuation, "
        "filler words and minor transcription errors - grade the substance only. "
        "Be fair but honest: do not inflate scores for vague or incorrect answers."
    )

    exchange = ""
    if follow_ups:
        lines = "\n".join(f"Interviewer: {q}\nCandidate: {a}" for q, a in follow_ups)
        exchange = (
            "\n\nThe interviewer then asked follow-up questions. Grade the whole exchange - "
            "a follow-up reply can add depth or correct an earlier mistake:\n" + lines
        )

    user_prompt = f"""Question asked:
{question}

Candidate's transcribed answer:
{transcript}{exchange}

Score each criterion from 0 to 10:
- correctness: is the substance factually right?
- depth: does it go beyond a surface-level response?
- relevance: does it actually answer the question asked?
- clarity: is the explanation well structured and easy to follow?

Then write `feedback` as 2-3 sentences addressed directly to the candidate
("you"), naming what specifically to fix."""

    result = await chat_json(
        system_prompt, user_prompt, SCORE_SCHEMA, temperature=0.2, max_tokens=200
    )

    rubric = {k: _clamp(result.get(k, 0)) for k in RUBRIC_WEIGHTS}
    content_score = round(sum(rubric[k] * w for k, w in RUBRIC_WEIGHTS.items()) * 10, 1)

    return {
        **rubric,
        "content_score": content_score,
        "feedback": result.get("feedback", "").strip(),
    }


async def summarise_session(role: str, answered: list[dict]) -> dict:
    """Produce session-level strengths and improvements once, at the end.

    Takes the per-answer feedback already generated during the interview, so
    this is one short call rather than extra tokens on every answer.
    """
    if not answered:
        return {"strengths": [], "improvements": []}

    lines = []
    for i, q in enumerate(answered, 1):
        lines.append(
            f"{i}. [{q.get('topic', 'question')}, scored {q.get('content_score')}/100] "
            f"{q.get('feedback_text', '')}"
        )

    system_prompt = (
        f"You are summarising a candidate's performance across {ROLE_BRIEFS.get(role, ROLE_BRIEFS['SDE'])}. "
        "Write for the candidate, in the second person."
    )
    user_prompt = (
        "Per-question feedback from the session:\n\n"
        + "\n".join(lines)
        + "\n\nIdentify the recurring themes. Give 2-4 `strengths` and 2-4 `improvements`, "
        "each a short phrase (under 12 words). Describe patterns across the session, not "
        "one-off remarks about a single answer."
    )

    result = await chat_json(
        system_prompt, user_prompt, SUMMARY_SCHEMA, temperature=0.3, max_tokens=260
    )
    return {
        "strengths": [s.strip() for s in result.get("strengths", []) if s.strip()][:4],
        "improvements": [s.strip() for s in result.get("improvements", []) if s.strip()][:4],
    }


def _clamp(value) -> int:
    try:
        return max(0, min(10, int(value)))
    except (TypeError, ValueError):
        return 0


def _empty_answer_result() -> dict:
    """Scoring a silent/empty answer needs no model call."""
    return {
        "correctness": 0,
        "depth": 0,
        "relevance": 0,
        "clarity": 0,
        "content_score": 0.0,
        "feedback": "No answer was recorded for this question.",
    }
