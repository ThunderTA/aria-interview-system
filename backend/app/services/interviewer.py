"""The interviewer's spoken side of a conversational interview.

Separate from llm_judge on purpose: grading is slow, careful and never read
aloud, whereas everything here is spoken mid-conversation - so it is short,
runs at interactive priority, and is written for the ear.
"""

import random
import re

from app.services.llm_client import chat_json
from app.services.llm_judge import ROLE_BRIEFS

REPLY_SCHEMA = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
}

NEXT_QUESTION, FOLLOW_UP, CLARIFY = "next_question", "follow_up", "clarify"

# Moving on is always said with one of these rather than generated: the model
# doesn't know the next question, and left to itself it announces a topic
# ("let's move on to your Docker setup") that the question then contradicts.
TRANSITIONS = (
    "Thanks, let's move on.",
    "Okay, thank you. Next question.",
    "Got it. Let's go to the next one.",
    "Thanks for that. Moving on.",
    "Alright, thank you.",
)

# Praise like "that's a great approach" grades the candidate out loud and
# coaches them mid-interview. The model does it anyway, so an evaluative
# opening sentence is stripped before the reply is spoken.
_PRAISE_OPENER = re.compile(
    r"^\s*(?:"
    r"that(?:'s| is| was| sounds(?: like)?| seems(?: like)?)\s+(?:a\s+|an\s+)?(?:really\s+|very\s+)?"
    r"(?:good|great|excellent|solid|nice|perfect|fantastic|strong|smart|thoughtful|reasonable)\b[^.!?]*[.!?]"
    r"|(?:great|good|excellent|nice|perfect|awesome|fantastic)"
    r"(?:\s+(?:answer|point|question|job|start|thinking|approach))?[.!,]"
    r")\s*",
    re.IGNORECASE,
)


def _persona(role: str) -> str:
    brief = ROLE_BRIEFS.get(role, ROLE_BRIEFS["SDE"])
    return (
        f"You are ARIA, a warm, professional interviewer on a live voice call, conducting {brief}. "
        "Everything you write is read aloud by a text-to-speech voice, so write plain spoken "
        "sentences: no lists, markdown, emojis, parentheses or code. Keep it brief. Never give "
        "away answers or hints, and never evaluate the candidate out loud - do not call anything "
        "good, great, solid or interesting. A neutral 'thanks' or 'got it' is fine."
    )


def _clean(text: str) -> str:
    return " ".join(str(text).replace("*", " ").split())


def _without_praise(text: str) -> str:
    stripped = _PRAISE_OPENER.sub("", text, count=1).strip()
    return stripped[:1].upper() + stripped[1:] if stripped else text


def _transcript(exchange: list[dict]) -> str:
    return "\n".join(
        f"{'Interviewer' if turn['speaker'] == 'interviewer' else 'Candidate'}: {turn['text']}"
        for turn in exchange
    )


async def reply_to_introduction(role: str, introduction: str) -> str:
    """One sentence acknowledging the candidate's self-introduction."""
    result = await chat_json(
        _persona(role),
        "You asked the candidate to introduce themselves. They said:\n"
        f"{introduction}\n\n"
        "Reply with ONE short sentence acknowledging one specific thing they mentioned. "
        "Do not ask a question - the first interview question follows straight after.",
        REPLY_SCHEMA,
        temperature=0.6,
        max_tokens=50,
    )
    return _without_praise(_clean(result.get("reply", ""))) or "Thanks for that."


async def next_move(
    role: str,
    question: str,
    exchange: list[dict],
    *,
    allow_follow_up: bool,
    allow_clarify: bool,
    follow_ups_asked: int = 0,
) -> dict:
    """Decide how to respond to the candidate's latest reply on one question.

    Returns {action, reply, quality}. The allowed actions are enforced by the
    JSON schema's enum, so a follow-up can't be chosen once the limit is hit.
    `quality` is a quick 0-10 impression used to pick the next question's
    difficulty before the full rubric score is ready.
    """
    actions = [NEXT_QUESTION]
    options = [
        f'- "{NEXT_QUESTION}": the question has been answered well enough to judge, or the '
        "candidate clearly doesn't know. `reply` is just a brief neutral acknowledgement."
    ]
    if allow_follow_up:
        actions.append(FOLLOW_UP)
        options.append(
            f'- "{FOLLOW_UP}": the answer is vague, incomplete, or skips something the question '
            "asked for. `reply` is one specific follow-up question about what they actually said. "
            "Most questions need one follow-up at most."
        )
    if allow_clarify:
        actions.append(CLARIFY)
        options.append(
            f'- "{CLARIFY}": ONLY when the candidate\'s last message makes no attempt to answer and '
            "explicitly asks you to repeat, rephrase or explain the question. A weak or off-topic "
            "answer is not a request to clarify. `reply` restates the question more clearly without "
            "hinting at the answer."
        )

    asked = (
        f"You have already asked {follow_ups_asked} follow-up question"
        f"{'' if follow_ups_asked == 1 else 's'} about this question, so move on unless the latest "
        "reply is clearly incomplete.\n\n"
        if follow_ups_asked
        else ""
    )
    schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": actions},
            "reply": {"type": "string"},
            "quality": {"type": "integer", "minimum": 0, "maximum": 10},
        },
        "required": ["action", "reply", "quality"],
    }
    user_prompt = (
        f"The interview question under discussion:\n{question}\n\n"
        f"The conversation about it so far:\n{_transcript(exchange)}\n\n"
        f"{asked}"
        "Decide what to do next. Choose one action:\n"
        + "\n".join(options)
        + "\n\nAlso give `quality`: a strict 0-10 rating of how well the candidate has answered the "
        "question so far - 0 to 3 if vague, off-topic or wrong, 5 if adequate, 8 or more only if "
        "correct, specific and complete."
    )

    result = await chat_json(_persona(role), user_prompt, schema, temperature=0.5, max_tokens=90)

    action = result.get("action") if result.get("action") in actions else NEXT_QUESTION
    reply = _without_praise(_clean(result.get("reply", "")))
    if action == NEXT_QUESTION or not reply:
        action, reply = NEXT_QUESTION, random.choice(TRANSITIONS)
    try:
        quality = max(0, min(10, int(result.get("quality", 5))))
    except (TypeError, ValueError):
        quality = 5
    return {"action": action, "reply": reply, "quality": quality}


async def answer_candidate_question(role: str, message: str) -> str:
    """Respond to "do you have any questions for me?" - briefly, without the goodbye."""
    result = await chat_json(
        _persona(role),
        "You asked whether the candidate has any questions for you. They said:\n"
        f"{message}\n\n"
        "If they asked something, answer briefly and honestly in one or two sentences. You are a "
        "practice interviewer, so for specifics about a real company or team, say those are best "
        "asked in their actual interview. If they have no questions, just say 'No problem.' "
        "Do not wish them luck, thank them or say goodbye - a closing line that does all of "
        "that follows.",
        REPLY_SCHEMA,
        temperature=0.5,
        max_tokens=80,
    )
    return _clean(result.get("reply", "")) or "No problem."
