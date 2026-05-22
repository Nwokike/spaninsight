"""AI Gateway client and utility functions."""

from __future__ import annotations

import logging
import re
from core.constants import API_HEALTH_ENDPOINT, API_CHAT_ENDPOINT, USER_AGENT
from services.api_client import get_client, request_with_retry

logger = logging.getLogger(__name__)

# Pre-compiled regular expressions for robust extraction
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_PYTHON_BLOCK_RE = re.compile(r"```python\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_GENERIC_BLOCK_RE = re.compile(r"```\s*(.*?)\s*```", re.DOTALL)

# Timeouts per task type matching the gateway's processing scale
TIMEOUTS = {
    "suggest": 60.0,
    "code": 60.0,
    "interpret": 60.0,
    "vision": 60.0,
    "audio": 60.0,
}


async def check_health() -> bool:
    """Ping the gateway health endpoint. Returns True if online."""
    try:
        client = get_client()
        resp = await client.get(
            API_HEALTH_ENDPOINT,
            headers={"User-Agent": USER_AGENT},
            timeout=5.0,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.warning("Gateway health check failed: %s", e)
        return False


async def call_gateway(task_type: str, messages: list[dict]) -> dict:
    """Make a non-streaming POST to the gateway with retry and expanded processing thresholds."""
    payload = {
        "task_type": task_type,
        "stream": False,
        "messages": messages,
    }
    timeout = TIMEOUTS.get(task_type, 20.0)

    resp = await request_with_retry(
        "POST",
        API_CHAT_ENDPOINT,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


async def call_gateway_raw(payload: dict, timeout: float = 15.0) -> dict:
    """Make a raw POST to the gateway with active connection parameters."""
    resp = await request_with_retry(
        "POST",
        API_CHAT_ENDPOINT,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def extract_content(data: dict) -> str:
    """Extract assistant payload content while handling thinking steps safely."""
    try:
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "") or ""
            content = strip_thinking(content)
            return content.strip()
    except (IndexError, KeyError, TypeError):
        pass
    return ""


def strip_thinking(text: str) -> str:
    """Remove <think>...</think> reasoning blocks using efficient pre-compiled matching."""
    return _THINK_RE.sub("", text).strip()


def extract_block_by_pattern(text: str, is_json: bool = False) -> str:
    """Uses advanced Regex pattern matching to pull code arrays safely."""
    cleaned = strip_thinking(text)

    if is_json:
        match = _JSON_BLOCK_RE.search(cleaned)
        if match:
            return match.group(1).strip()
    else:
        match = _PYTHON_BLOCK_RE.search(cleaned)
        if match:
            return match.group(1).strip()

    generic_match = _GENERIC_BLOCK_RE.search(cleaned)
    if generic_match:
        return generic_match.group(1).strip()

    for trim_target in ["```python", "```json", "```"]:
        if cleaned.lower().startswith(trim_target):
            cleaned = cleaned[len(trim_target) :]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    return cleaned.strip()
