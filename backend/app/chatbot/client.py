"""
OpenRouter Client
=================
Thin HTTP wrapper around OpenRouter chat completions API.

Uses ``httpx`` for a synchronous interface with configurable timeouts.
API keys are read from backend environment variables only.
"""

import logging
from typing import Optional

import httpx

from app.core.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL_NAME,
    OPENROUTER_REASONING_EFFORT,
    OPENROUTER_TEMPERATURE,
    OPENROUTER_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when OpenRouter is unreachable or returns an error."""


# Backward-compatible alias for existing imports.
OllamaError = LLMError


def _extract_answer_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                txt = item.get("text")
                if txt:
                    parts.append(str(txt))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).strip()
    return ""


def generate(
    prompt: str,
    model: Optional[str] = None,
    num_predict: Optional[int] = None,
    timeout: Optional[float] = None,
) -> str:
    """
    Send a prompt to OpenRouter and return the generated text.

    Parameters
    ----------
    prompt : str
        The full prompt (system + context + question), already assembled.
    model : str, optional
        Override the default model name.
    num_predict : int, optional
        Maximum number of tokens to generate. When ``None``, provider defaults are used.

    Returns
    -------
    str
        The LLM-generated answer text.
    """
    if not OPENROUTER_API_KEY:
        raise LLMError("OPENROUTER_API_KEY is not configured on the backend.")

    model_name = model or OPENROUTER_MODEL_NAME
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": OPENROUTER_TEMPERATURE,
    }
    if OPENROUTER_REASONING_EFFORT in {"low", "medium", "high"}:
        payload["reasoning"] = {"effort": OPENROUTER_REASONING_EFFORT}
    if num_predict is not None:
        payload["max_tokens"] = int(num_predict)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # A caller with its own deadline may shorten this, never lengthen it. The
    # default (240s) outlives the SPA's 180s abort, so an unbounded call can
    # only ever finish after the user has already been shown a timeout.
    effective_timeout = OPENROUTER_TIMEOUT_SECONDS
    if timeout is not None:
        effective_timeout = max(5.0, min(float(timeout), float(OPENROUTER_TIMEOUT_SECONDS)))

    try:
        logger.info(
            "Sending request to OpenRouter [%s] (timeout=%.0fs) ...", model_name, effective_timeout
        )
        with httpx.Client(timeout=effective_timeout) as client:
            resp = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
    except httpx.ConnectError as exc:
        raise LLMError("Cannot connect to OpenRouter API endpoint.") from exc
    except httpx.TimeoutException:
        raise LLMError(
            f"OpenRouter request timed out after {effective_timeout:.0f}s."
        )
    except httpx.HTTPStatusError as exc:
        raise LLMError(f"OpenRouter returned HTTP {exc.response.status_code}: {exc.response.text}")

    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise LLMError("OpenRouter returned no choices.")

    message = choices[0].get("message") or {}
    answer = _extract_answer_text(message)
    finish_reason = choices[0].get("finish_reason")

    # Some free-tier reasoning models spend most tokens on hidden reasoning and clip visible output.
    if finish_reason == "length" and len(answer) < 260:
        retry_max_tokens = max(1200, int((num_predict or 600) * 2))
        retry_payload = dict(payload)
        retry_payload["max_tokens"] = min(retry_max_tokens, 2400)
        retry_payload["messages"] = [
            {
                "role": "user",
                "content": prompt + "\n\nIMPORTANT: Return only final answer text with concise section bullets. Avoid long internal reasoning.",
            }
        ]
        try:
            with httpx.Client(timeout=OPENROUTER_TIMEOUT_SECONDS) as client:
                retry_resp = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=retry_payload,
                )
                retry_resp.raise_for_status()
            retry_data = retry_resp.json()
            retry_choices = retry_data.get("choices") or []
            if retry_choices:
                retry_message = retry_choices[0].get("message") or {}
                retry_answer = _extract_answer_text(retry_message)
                if len(retry_answer) > len(answer):
                    answer = retry_answer
                    data = retry_data
                    choices = retry_choices
                    finish_reason = retry_choices[0].get("finish_reason")
        except Exception:
            pass

    if not answer:
        usage = data.get("usage") or {}
        completion_details = usage.get("completion_tokens_details") or {}
        reasoning_tokens = completion_details.get("reasoning_tokens")
        completion_tokens = usage.get("completion_tokens")
        raise LLMError(
            "OpenRouter returned empty text "
            f"(finish_reason={finish_reason}, completion_tokens={completion_tokens}, reasoning_tokens={reasoning_tokens})."
        )

    logger.info("OpenRouter responded - %d chars", len(answer))
    return answer


def is_available() -> bool:
    """Check whether OpenRouter key appears valid and provider reachable."""
    if not OPENROUTER_API_KEY:
        return False

    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            )
            return resp.status_code == 200
    except Exception:
        return False
