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
    TASK_SUGGEST: 25.0,
    TASK_CODE: 45.0,
    TASK_INTERPRET: 20.0,
    TASK_VISION: 40.0,
    TASK_AUDIO: 30.0,
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


async def describe_dataset(schema_json: dict) -> str:
    """Block 0 describe: AI reads the schema and describes the dataset."""
    system_prompt = (
        "You are a data analyst. Given a dataset schema with column names, "
        "types, and sample statistics, write a brief 2-3 sentence description "
        "of what this dataset contains and what kind of data it represents. "
        "Be specific about the domain (healthcare, finance, education, etc.). "
        "Do NOT use markdown. Just plain text."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(schema_json, default=str)},
    ]
    try:
        data = await _call_gateway(TASK_SUGGEST, messages)
        desc = _extract_content(data)
        if desc:
            logger.info("Block 0 describe: %s", desc[:80])
            return desc
        return "Dataset loaded successfully."
    except Exception as e:
        logger.error("Describe dataset failed: %s", e)
        return "Dataset loaded. AI description unavailable."


async def describe_result(
    initial_description: str,
    latest_result: dict,
) -> str:
    """Block N describe: AI describes what a specific analysis result shows.

    Context = Block 0 description + latest block's code/stdout/result.
    """
    system_prompt = (
        "You are a data analyst writing for a student. "
        "Describe what this analysis result shows in 2-3 clear sentences. "
        "Mention specific numbers, trends, or patterns. "
        "Do NOT use markdown. Just plain text."
    )
    context = (
        f"Dataset: {initial_description}\n\n"
        f"Analysis: {latest_result.get('prompt', '')}\n"
        f"Code:\n{latest_result.get('code', '')}\n\n"
        f"Output: {latest_result.get('stdout', '')}\n"
        f"Result: {latest_result.get('result', '')}"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context},
    ]
    try:
        data = await _call_gateway(TASK_INTERPRET, messages)
        desc = _extract_content(data)
        if desc:
            logger.info("Block N describe: %s", desc[:80])
            return desc
        return "Analysis completed."
    except Exception as e:
        logger.error("Describe result failed: %s", e)
        return "Analysis completed."


async def suggest(
    schema_json: dict,
    initial_description: str = "",
    latest_result: dict | None = None,
) -> list[dict]:
    """Context-aware suggestions. Uses Block 0 + last block for smarter picks.

    Each suggestion: {"label": str, "icon": str, "prompt": str}
    """
    system_prompt = (
        "You are a data analysis assistant. Suggest exactly 3 NEW insightful "
        "analyses the user should perform next based on the dataset and any "
        "previous analysis context. Do NOT repeat previous analyses. "
        "Return ONLY a JSON array of 3 objects, each with:\n"
        '- "label": short title (max 4 words)\n'
        '- "icon": a single relevant emoji\n'
        '- "prompt": the full analysis instruction to generate pandas/matplotlib code\n'
        "Do not include any text outside the JSON array."
    )
    context_parts = [json.dumps(schema_json, default=str)]
    if initial_description:
        context_parts.append(f"\nDataset: {initial_description}")
    if latest_result:
        context_parts.append(
            f"\nLast analysis: {latest_result.get('prompt', '')}"
            f"\nResult: {latest_result.get('result', '')}"
            f"\nDescription: {latest_result.get('description', '')}"
        )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n".join(context_parts)},
    ]
    try:
        data = await _call_gateway(TASK_SUGGEST, messages)
        content = _extract_content(data)
        cleaned = _strip_code_fences(content)
        suggestions = json.loads(cleaned)
        if isinstance(suggestions, list):
            return suggestions[:3]
        return []
    except Exception as e:
        logger.error("Suggest failed: %s", e)
        return fallback_suggestions()


async def generate_code(prompt: str, schema_json: dict) -> str:
    """Send an analysis prompt to the code route. Returns Python code string.

    Uses a SLIM schema (columns + types only) to avoid token bloat
    on the heavy reasoning models (nvidia). The full schema is too large.
    """
    # Build slim schema: just what the model needs to write code
    slim = {
        "shape": schema_json.get("shape", {}),
        "columns": [
            {"name": c["name"], "dtype": c["dtype"]}
            for c in schema_json.get("columns", [])
        ],
    }

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
        f"Dataset schema:\n{json.dumps(slim, default=str)}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        data = await _call_gateway(TASK_CODE, messages)
        content = _extract_content(data)
        code = _strip_code_fences(content)
        if not code.strip():
            logger.error("Code generation returned empty content. Raw: %s", str(data)[:200])
        return code
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


async def generate_form_schema(prompt: str) -> dict | None:
    """Use the suggest route to generate a form schema from a natural language description.

    Returns a dict with "title", "description", "fields" keys, or None on failure.
    """
    system_prompt = (
        "You are a form builder AI. Given a description of a survey or questionnaire, "
        "generate a JSON object with:\n"
        '- "title": the form title\n'
        '- "description": a brief description\n'
        '- "fields": an array of field objects, each with:\n'
        '  - "name": field identifier (snake_case)\n'
        '  - "label": display label\n'
        '  - "type": one of "text", "number", "email", "select", "radio", "checkbox", "textarea"\n'
        '  - "required": boolean\n'
        '  - "options": array of strings (only for select/radio/checkbox)\n'
        "Return ONLY the JSON object. No markdown fences."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        data = await _call_gateway(TASK_SUGGEST, messages)
        content = _extract_content(data)
        cleaned = _strip_code_fences(content)
        return json.loads(cleaned)
    except Exception as e:
        logger.error("AI form gen failed: %s", e)
        return None


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
    """Extract the assistant's message content from an OpenAI-format response.

    Handles thinking models (nvidia nemotron etc.) that may include
    <think>...</think> blocks in the content field.
    """
    try:
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "") or ""
            # Strip thinking tags from nvidia reasoning models
            content = _strip_thinking(content)
            return content.strip()
    except (IndexError, KeyError, TypeError):
        pass
    return ""


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks from reasoning model output."""
    import re
    # Remove <think>...</think> blocks (greedy, handles multiline)
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return cleaned.strip()


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from AI output."""
    cleaned = text.strip()
    # Strip thinking tags first
    cleaned = _strip_thinking(cleaned)
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


def fallback_suggestions() -> list[dict]:
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
