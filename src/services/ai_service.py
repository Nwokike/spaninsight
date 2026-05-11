"""AI Gateway client — talks to the live Cloudflare Worker.

Endpoint: https://api.spaninsight.com/chat
Auth: X-App-Secret + User-Agent headers
Task types: suggest, code, interpret, vision, audio

Spaninsight Eye (vision) and Spaninsight Voice (audio) follow the Akili pattern:
- Eye: image → vision model describes it → text description fed to main AI
- Voice: audio → Whisper transcribes it → transcript fed to main AI
"""

from __future__ import annotations

import base64
import json
import logging

import httpx

from core.constants import (
    API_CHAT_ENDPOINT,
    API_HEALTH_ENDPOINT,
    APP_SECRET,
    MAX_VOICE_DURATION_SEC,
    TASK_CODE,
    TASK_INTERPRET,
    TASK_SUGGEST,
    TASK_VISION,
    TASK_AUDIO,
    USER_AGENT,
)

logger = logging.getLogger(__name__)

# Shared headers for every request
_HEADERS = {
    "X-App-Secret": APP_SECRET,
    "User-Agent": USER_AGENT,
    "Content-Type": "application/json",
}

# Timeouts per task type (match gateway's own timeouts)
_TIMEOUTS = {
    TASK_SUGGEST: 15.0,
    TASK_CODE: 30.0,
    TASK_INTERPRET: 15.0,
    TASK_VISION: 28.0,
    TASK_AUDIO: 20.0,
}


async def check_health() -> bool:
    """Ping the gateway health endpoint. Returns True if online."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                API_HEALTH_ENDPOINT,
                headers={"User-Agent": USER_AGENT},
                timeout=5.0,
            )
            return resp.status_code == 200
    except Exception as e:
        logger.warning("Gateway health check failed: %s", e)
        return False


# ── Spaninsight Eye (Vision) ────────────────────────────────────────

async def analyze_image(image_bytes: bytes, mime_type: str) -> str:
    """Send an image to the vision model for detailed description.

    Akili Eye pattern: the vision model describes the image in text,
    which is then fed to the main AI as context — NOT raw multimodal.

    Returns a text description of the image content.
    """
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "You are Spaninsight Eye. Describe this image in extreme detail. "
                        "If it contains a chart, table, or data visualization, extract all "
                        "visible numbers, labels, axes, and trends. If it contains text, "
                        "transcribe every word. Be thorough and precise."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64_image}"},
                },
            ],
        }],
        "task_type": TASK_VISION,
        "temperature": 0.2,
        "max_tokens": 2048,
    }

    try:
        data = await _call_gateway_raw(payload, timeout=28.0)
        content = _extract_content(data)
        if content:
            logger.info("Spaninsight Eye: described %d bytes image → %d chars", len(image_bytes), len(content))
            return content
        return "[Image analysis failed — no description returned]"
    except Exception as e:
        logger.error("Spaninsight Eye failed: %s", e)
        return f"[Image analysis failed: {e}]"


# ── Spaninsight Voice (Audio → Whisper) ─────────────────────────────

async def transcribe_audio(audio_bytes: bytes, mime_type: str) -> str:
    """Send audio to Whisper for transcription.

    Akili Ear pattern: Whisper transcribes the voice note to text,
    which is then fed to the main AI as context.

    Max recording: 60 seconds. Max size: 25MB (gateway limit).

    Returns transcribed text.
    """
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            files = {"file": ("audio.wav", audio_bytes, mime_type)}
            form_data = {"task_type": TASK_AUDIO}

            resp = await client.post(
                API_CHAT_ENDPOINT,
                headers={
                    "X-App-Secret": APP_SECRET,
                    "User-Agent": USER_AGENT,
                    # DO NOT set Content-Type — httpx sets multipart/form-data automatically
                },
                files=files,
                data=form_data,
            )

            if resp.status_code != 200:
                logger.error("Whisper HTTP %d: %s", resp.status_code, resp.text[:200])
                return "[Transcription failed — server error]"

            data = resp.json()
            # Whisper response format from Groq
            transcript = data.get("text", "")
            if not transcript:
                transcript = _extract_content(data)

            if transcript:
                logger.info("Spaninsight Voice: transcribed %d bytes audio → '%s'", len(audio_bytes), transcript[:80])
                return transcript
            return "[Transcription returned empty result]"

    except Exception as e:
        logger.error("Spaninsight Voice failed: %s", e)
        return f"[Transcription failed: {e}]"


# ── Standard AI Endpoints ───────────────────────────────────────────

async def suggest(schema_json: dict) -> list[dict]:
    """Send data schema to the suggest route. Returns list of suggestion dicts.

    Each suggestion: {"label": str, "icon": str, "prompt": str}
    """
    system_prompt = (
        "You are a data analysis assistant. Given a dataset schema, "
        "suggest exactly 3 insightful analyses the user could perform. "
        "Return ONLY a JSON array of 3 objects, each with:\n"
        '- "label": short title (max 6 words)\n'
        '- "icon": a relevant emoji\n'
        '- "prompt": the full analysis instruction to generate pandas/matplotlib code\n'
        "Do not include any text outside the JSON array."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(schema_json, default=str)},
    ]

    try:
        data = await _call_gateway(TASK_SUGGEST, messages)
        content = _extract_content(data)

        # Parse the JSON array from the response
        cleaned = _strip_code_fences(content)
        suggestions = json.loads(cleaned)
        if isinstance(suggestions, list):
            return suggestions[:3]
        return []

    except Exception as e:
        logger.error("Suggest failed: %s", e)
        return _fallback_suggestions()


async def generate_code(prompt: str, schema_json: dict) -> str:
    """Send an analysis prompt to the code route. Returns Python code string."""
    system_prompt = (
        "You are a Python data analyst. Generate pandas and matplotlib code "
        "to analyze the DataFrame `df` based on the user's request.\n\n"
        "Rules:\n"
        "- The DataFrame is already loaded as `df`. Do NOT import or load data.\n"
        "- You may use: pandas (as pd), numpy (as np), matplotlib.pyplot (as plt)\n"
        "- Always call plt.tight_layout() before the end\n"
        "- Store any key numeric result in a variable called `result`\n"
        "- Do NOT use plt.show()\n"
        "- Do NOT use any file I/O, network, or system operations\n"
        "- Return ONLY the Python code, no markdown fences, no explanation\n\n"
        f"Dataset schema:\n{json.dumps(schema_json, default=str)}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        data = await _call_gateway(TASK_CODE, messages)
        content = _extract_content(data)
        return _strip_code_fences(content)
    except Exception as e:
        logger.error("Code generation failed: %s", e)
        return ""


async def interpret(result_data: dict) -> str:
    """Send execution results to the interpret route. Returns insight text."""
    system_prompt = (
        "You are a data analyst writing for a university student. "
        "Given the numerical results and code output from a data analysis, "
        "write a clear, concise 2-3 sentence interpretation. "
        "Use plain language. Mention specific numbers. "
        "Do NOT use markdown formatting. Just plain text."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(result_data, default=str)},
    ]

    try:
        data = await _call_gateway(TASK_INTERPRET, messages)
        return _extract_content(data)
    except Exception as e:
        logger.error("Interpret failed: %s", e)
        return "Analysis complete. See the chart above for details."


async def analyze_image_for_data(image_bytes: bytes, mime_type: str, schema_json: dict) -> str:
    """Eye + Code combo: describe an image, then generate analysis code from it.

    Useful when user takes a photo of a chart/table and wants AI to analyze it.
    """
    description = await analyze_image(image_bytes, mime_type)

    prompt = (
        f"The user uploaded an image. Here is what Spaninsight Eye extracted:\n\n"
        f"{description}\n\n"
        f"Based on this context and the loaded dataset, generate analysis code."
    )

    return await generate_code(prompt, schema_json)


# ── Private helpers ─────────────────────────────────────────────────


async def _call_gateway(task_type: str, messages: list[dict]) -> dict:
    """Make a non-streaming POST to the gateway."""
    payload = {
        "task_type": task_type,
        "stream": False,
        "messages": messages,
    }
    timeout = _TIMEOUTS.get(task_type, 15.0)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            API_CHAT_ENDPOINT,
            headers=_HEADERS,
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()


async def _call_gateway_raw(payload: dict, timeout: float = 15.0) -> dict:
    """Make a raw POST (custom payload) to the gateway."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            API_CHAT_ENDPOINT,
            headers=_HEADERS,
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()


def _extract_content(data: dict) -> str:
    """Extract the assistant's message content from an OpenAI-format response."""
    try:
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            return message.get("content", "")
    except (IndexError, KeyError, TypeError):
        pass
    return ""


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from AI output."""
    cleaned = text.strip()
    if cleaned.startswith("```python"):
        cleaned = cleaned[len("```python"):]
    elif cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):]
    elif cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:])
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _fallback_suggestions() -> list[dict]:
    """Return default suggestions when the AI is unavailable."""
    return [
        {
            "label": "Summary Statistics",
            "icon": "📊",
            "prompt": "Show descriptive statistics for all numeric columns as a styled table.",
        },
        {
            "label": "Distribution Plot",
            "icon": "📈",
            "prompt": "Plot histograms of all numeric columns in a grid layout.",
        },
        {
            "label": "Correlation Heatmap",
            "icon": "🔥",
            "prompt": "Create a correlation heatmap of all numeric columns with annotations.",
        },
    ]
