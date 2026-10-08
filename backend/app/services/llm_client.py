"""Thin async client for the LLM backend.

Targets a local Ollama server by default (no API key, runs offline), but only
depends on the /api/chat contract, so swapping in another provider means
rewriting this module alone - the judging logic in llm_judge.py is unaffected.

Uses Ollama's structured-output support: passing a JSON Schema as `format`
constrains decoding so responses parse reliably instead of needing the model to
be politely asked for JSON.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(RuntimeError):
    """The LLM backend could not be reached or did not return usable output."""


class _PriorityGate:
    """One request at a time, with interactive work ahead of background work.

    Ollama generates one response at a time, so a rubric-scoring request queued
    just before the interviewer's next line would delay it. Serialising here
    lets an interactive request go next instead. A request already running is
    never interrupted.
    """

    def __init__(self) -> None:
        self._condition: asyncio.Condition | None = None
        self._busy = False
        self._interactive_waiting = 0

    @asynccontextmanager
    async def slot(self, *, background: bool):
        if self._condition is None:
            self._condition = asyncio.Condition()
        condition = self._condition

        async with condition:
            if not background:
                self._interactive_waiting += 1
            try:
                await condition.wait_for(
                    lambda: not self._busy and (not background or self._interactive_waiting == 0)
                )
            finally:
                if not background:
                    self._interactive_waiting -= 1
                    # A cancelled interactive waiter may have been all that
                    # was holding background work back.
                    condition.notify_all()
            self._busy = True

        try:
            yield
        finally:
            async with condition:
                self._busy = False
                condition.notify_all()


_gate = _PriorityGate()


async def chat_json(
    system_prompt: str,
    user_prompt: str,
    schema: dict,
    *,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    background: bool = False,
) -> dict:
    """Run a chat completion constrained to `schema` and return the parsed object.

    `max_tokens` matters more than it looks: local generation is output-token
    bound, so capping the response is the main lever on how long a candidate
    waits mid-interview. `background` marks work nobody is waiting on in real
    time, such as scoring a finished answer, which yields to everything else.
    """
    options: dict = {"temperature": temperature}
    if max_tokens is not None:
        options["num_predict"] = max_tokens

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "format": schema,
        "stream": False,
        "options": options,
    }

    try:
        async with _gate.slot(background=background):
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                response = await client.post(f"{settings.llm_base_url}/api/chat", json=payload)
                response.raise_for_status()
                body = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:200]
        if exc.response.status_code == 404:
            raise LLMUnavailableError(
                f"Model '{settings.llm_model}' is not available. "
                f"Run: ollama pull {settings.llm_model}"
            ) from exc
        raise LLMUnavailableError(f"LLM request failed ({exc.response.status_code}): {detail}") from exc
    except httpx.RequestError as exc:
        raise LLMUnavailableError(
            f"Could not reach the LLM at {settings.llm_base_url}. Is `ollama serve` running?"
        ) from exc

    content = body.get("message", {}).get("content", "")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning("LLM returned unparseable JSON: %r", content[:300])
        raise LLMUnavailableError("The LLM returned malformed output. Try again.") from exc


async def is_available() -> bool:
    """Check whether the LLM backend is reachable and has the configured model."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.llm_base_url}/api/tags")
            response.raise_for_status()
            models = {m.get("name", "") for m in response.json().get("models", [])}
    except (httpx.HTTPError, ValueError):
        return False

    # Ollama reports "qwen2.5:7b"; tolerate a configured name without the tag.
    return any(name == settings.llm_model or name.split(":")[0] == settings.llm_model.split(":")[0]
               for name in models)
