"""Thin async client for the LLM backend.

Targets a local Ollama server by default (no API key, runs offline), but only
depends on the /api/chat contract, so swapping in another provider means
rewriting this module alone — the judging logic in llm_judge.py is unaffected.

Uses Ollama's structured-output support: passing a JSON Schema as `format`
constrains decoding so responses parse reliably instead of needing the model to
be politely asked for JSON.
"""

import json
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(RuntimeError):
    """The LLM backend could not be reached or did not return usable output."""


async def chat_json(
    system_prompt: str,
    user_prompt: str,
    schema: dict,
    *,
    temperature: float = 0.7,
) -> dict:
    """Run a chat completion constrained to `schema` and return the parsed object."""
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "format": schema,
        "stream": False,
        "options": {"temperature": temperature},
    }

    try:
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
