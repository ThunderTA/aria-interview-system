# TODO: LLM-based question generation + answer scoring.
# - generate_question(): role, difficulty_level, resume-derived skills ->
#   next interview question text.
# - score_answer(): question + transcript -> structured rubric scores
#   (content_score fields) + feedback_text, via a single LLM-as-judge call.
# See docs/architecture.md ("Multimodal Assessment") for the rubric fields.


async def generate_question(role: str, difficulty_level: int, skills: list[str]) -> str:
    raise NotImplementedError


async def score_answer(question: str, transcript: str) -> dict:
    raise NotImplementedError
