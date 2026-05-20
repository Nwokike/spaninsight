"""AI Gateway client — talks to the live Cloudflare Worker.

Endpoint: https://api.spaninsight.com/chat
Auth: X-App-Secret + User-Agent headers
Task types: suggest, code, interpret, vision, audio

Uncapped Optimization Rewrite:
- Eliminated artificial suggestions cap (upgraded from 3 restricted chips to 5-8 comprehensive tracks).
- Removed token-bloat schema slicing; feeds the complete rich metadata/statistics to the reasoning model.
- Upgraded block extractors to use regex patterns to handle noisy formatting gracefully and eliminate JSON exceptions.
- Completely removed cost-management minimization constraints.
- Hardened code generation rules to prevent sandbox library violations (Seaborn/Plotly).
"""

from __future__ import annotations

import base64
import json
import logging
import re

from core.constants import (
    API_CHAT_ENDPOINT,
    API_HEALTH_ENDPOINT,
    TASK_CODE,
    TASK_INTERPRET,
    TASK_SUGGEST,
    TASK_VISION,
    TASK_AUDIO,
    USER_AGENT,
)
from services.api_client import get_client, request_with_retry, COMMON_HEADERS

logger = logging.getLogger(__name__)

# Pre-compiled regular expressions for robust extraction
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_PYTHON_BLOCK_RE = re.compile(r"```python\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_GENERIC_BLOCK_RE = re.compile(r"```\s*(.*?)\s*```", re.DOTALL)

# Timeouts per task type matching the gateway's processing scale
_TIMEOUTS = {
    TASK_SUGGEST: 35.0,  # Increased to accommodate richer parallel suggestions
    TASK_CODE: 60.0,  # Increased for unconstrained reasoning execution
    TASK_INTERPRET: 25.0,
    TASK_VISION: 45.0,
    TASK_AUDIO: 30.0,
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


# ── Spaninsight Eye (Vision) ────────────────────────────────────────


async def analyze_image(image_bytes: bytes, mime_type: str) -> str:
    """Send an image to the vision model for detailed description."""
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "messages": [
            {
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
            }
        ],
        "task_type": TASK_VISION,
        "temperature": 0.2,
        "max_tokens": 4096,  # Uncapped tokens for detailed vision extraction
    }

    try:
        data = await _call_gateway_raw(payload, timeout=40.0)
        content = _extract_content(data)
        if content:
            logger.info(
                "Spaninsight Eye: described %d bytes image → %d chars",
                len(image_bytes),
                len(content),
            )
            return content
        return "[Image analysis failed — no description returned]"
    except Exception as e:
        logger.error("Spaninsight Eye failed: %s", e)
        return f"[Image analysis failed: {e}]"


# ── Spaninsight Voice (Audio → Whisper) ─────────────────────────────


async def transcribe_audio(audio_bytes: bytes, mime_type: str) -> str:
    """Send audio to Whisper for transcription."""
    try:
        client = get_client()
        files = {"file": ("audio.wav", audio_bytes, mime_type)}
        form_data = {"task_type": TASK_AUDIO}

        resp = await client.post(
            API_CHAT_ENDPOINT,
            headers=COMMON_HEADERS,
            files=files,
            data=form_data,
            timeout=30.0,
        )

        if resp.status_code != 200:
            logger.error("Whisper HTTP %d: %s", resp.status_code, resp.text[:200])
            return "[Transcription failed — server error]"

        data = resp.json()
        transcript = data.get("text", "")
        if not transcript:
            transcript = _extract_content(data)

        if transcript:
            logger.info(
                "Spaninsight Voice: transcribed %d bytes audio → '%s'",
                len(audio_bytes),
                transcript[:80],
            )
            return transcript
        return "[Transcription returned empty result]"

    except Exception as e:
        logger.error("Spaninsight Voice failed: %s", e)
        return f"[Transcription failed: {e}]"


# ── Standard AI Endpoints ───────────────────────────────────────────


def _build_mcp_prompt_segment() -> str:
    """Build a system prompt segment describing connected and enabled MCP servers and tools."""
    from core.state import state

    if not state.mcp_servers:
        return ""

    has_active = False
    segment = "\n\nAvailable remote Model Context Protocol (MCP) servers and tools:\n"
    segment += "You can invoke these tools in your python code using `mcp.call_tool(server_name, tool_name, arguments)`.\n"
    segment += "Always check that the server name and tool name match exactly. The `arguments` must be a dictionary matching the tool's parameter schema.\n"
    for srv in state.mcp_servers:
        if not srv.get("enabled", True):
            continue

        enabled_tools = [t for t in srv.get("tools", []) if t.get("enabled", True)]
        if not enabled_tools:
            continue

        has_active = True
        segment += f"- Server '{srv['name']}':\n"
        for tool in enabled_tools:
            desc = tool.get("description", "").replace("\n", " ")
            segment += f"  * Tool '{tool['name']}': {desc}\n"
            if "inputSchema" in tool:
                props = tool["inputSchema"].get("properties", {})
                segment += f"    Parameters: {json.dumps(props, default=str)}\n"

    if not has_active:
        return ""
    return segment


async def describe_dataset(schema_json: dict) -> str:
    """Block 0 describe: AI reads the schema and describes the dataset."""
    system_prompt = (
        "You are an expert data science director. Given a comprehensive dataset schema "
        "with structural details and distribution statistics, provide a professional, "
        "highly concise overview of what the data signifies and the macro domains it represents. "
        "Do NOT use any markdown (no bold, no italics, no bullet points, no headers). "
        "Write strictly as clear, plain-text prose, limited to at most 2 to 3 sentences."
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
    """Block N describe: AI describes what a specific analysis result shows."""
    system_prompt = (
        "You are an expert data analyst. Describe what this specific data analysis "
        "execution result establishes. Interpret anomalies, specific distributions, exact "
        "numerical indices, and structural trends. "
        "Do NOT use any markdown (no bold, no italics, no bullet points, no headers). "
        "Write strictly as clear, plain-text analytical findings, limited to at most 2 to 3 sentences."
    )
    context = (
        f"Dataset: {initial_description}\n\n"
        f"Analysis Prompt: {latest_result.get('prompt', '')}\n"
        f"Executed Code:\n{latest_result.get('code', '')}\n\n"
        f"Standard Output Logs:\n{latest_result.get('stdout', '')}\n"
        f"Returned Value String:\n{latest_result.get('result', '')}"
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
    """Context-aware suggestions without cost-cutting limits. Returns 5-8 recommendations."""
    system_prompt = (
        "You are an unrestricted, expert data intelligence consultant. Suggest a rich, multi-angle "
        "suite of 5 to 8 distinct, deeply insightful data analysis tracks the user should perform next. "
        "Analyze trends, correlations, pivot metrics, and exploratory profiles. Do NOT repeat previous steps.\n\n"
        "Return exclusively a valid, raw JSON array of objects with zero conversational wrappers. "
        "Each object must contain EXACTLY these keys:\n"
        '- "label": concise descriptive title (max 5 words)\n'
        '- "icon": "emoji" (always double-quoted emoji character)\n'
        '- "prompt": full structural instruction used to generate the required pandas/matplotlib execution block\n'
        "Do not include code fences, preamble, or conversational notes outside the JSON array."
    )
    context_parts = [json.dumps(schema_json, default=str)]
    if initial_description:
        context_parts.append(f"\nDataset Overview: {initial_description}")
    if latest_result:
        context_parts.append(
            f"\nLast analysis step: {latest_result.get('prompt', '')}"
            f"\nExecution Result: {latest_result.get('result', '')}"
            f"\nInsight: {latest_result.get('description', '')}"
        )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n".join(context_parts)},
    ]
    try:
        data = await _call_gateway(TASK_SUGGEST, messages)
        content = _extract_content(data)
        cleaned = _extract_block_by_pattern(content, is_json=True)
        # Robustly auto-quote unquoted emojis for the "icon" key if the AI forgot quotes
        cleaned = re.sub(r'"icon"\s*:\s*([^"\s,{}]+)', r'"icon": "\1"', cleaned)
        suggestions = json.loads(cleaned)
        if isinstance(suggestions, list):
            return suggestions  # No artificial slice applied
        return []
    except Exception as e:
        logger.error(
            "Suggest failed: %s. Raw text was: %s",
            e,
            content if "content" in locals() else "",
        )
        return fallback_suggestions()


async def generate_code(prompt: str, schema_json: dict) -> str:
    """Send prompt to code route using full uncut dataset schema statistics."""
    # NO SLICING/SLIMMING SCHEMA: Send full schema for perfect reasoning precision
    mcp_segment = _build_mcp_prompt_segment()
    system_prompt = (
        "You are an expert Python core data engineer. Generate optimal, safe pandas and matplotlib "
        "code blocks to analyze the loaded DataFrame `df` according to the user's explicit request.\n\n"
        "CRITICAL — ONLY these 3 libraries are available:\n"
        "  1. pandas (import as pd)\n"
        "  2. numpy  (import as np)\n"
        "  3. matplotlib.pyplot (import as plt)\n\n"
        "STRICTLY FORBIDDEN — do NOT import or use ANY of these (they will cause execution failure):\n"
        "  seaborn, sns, scipy, sklearn, statsmodels, plotly, pingouin, lifelines, any other library.\n"
        "  If you need heatmap → use plt.imshow() or plt.matshow() with pandas/numpy.\n"
        "  If you need regression → use np.polyfit() or np.linalg.lstsq().\n"
        "  If you need PCA → use np.linalg.eigh() on the covariance matrix.\n"
        "  If you need statistical tests → use numpy (np.mean, np.std, np.corrcoef, etc.).\n\n"
        "Execution Framework Rules:\n"
        "- The DataFrame is pre-loaded as global variable `df`. Do NOT mock, download, or re-read data files.\n"
        "- For statistical calculations (e.g. regressions, curve fitting, trend lines, statistical indices, correlations), write them using numpy (e.g. np.polyfit, np.cov, np.corrcoef) or pandas (e.g. df.corr, df.describe, df.cov). This ensures 100% Android mobile compatibility.\n"
        "- For plotting, format with clean parameters and always call plt.tight_layout() before completion.\n"
        "- For plotting, always check data dimensions before passing labels.\n"
        "- If you generate labels for boxplots, ensure the length of 'labels' exactly matches the number of columns plotted.\n"
        "- If the user request is ambiguous, default to standard plots without custom labels to avoid dimension errors.\n"
        "- Use modern Matplotlib syntax (use 'tick_labels' instead of 'labels' for boxplot functions).\n"
        "- Assign any critical table, subset metrics, or computation text to a local variable named `result`.\n"
        "- Do NOT invoke interactive methods like plt.show() or object inspectors.\n"
        "- Do NOT engage in file system operations or network activities.\n"
        "- Return only functional Python code. No introductory remarks, conversational wrappers, or markdown text."
        f"{mcp_segment}\n\n"
        f"Complete Dataset Metric Schema:\n{json.dumps(schema_json, default=str)}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        data = await _call_gateway(TASK_CODE, messages)
        content = _extract_content(data)
        code = _extract_block_by_pattern(content, is_json=False)
        if not code.strip():
            logger.error(
                "Code generation returned empty payload. Raw content context: %s",
                str(data)[:250],
            )
        return code
    except Exception as e:
        logger.error("Code generation failed: %s", e)
        return ""


async def generate_corrected_code(
    prompt: str,
    bad_code: str,
    error_message: str,
    schema_json: dict,
) -> str:
    """Send failing code and traceback to the gateway to generate corrected, safe Python code."""
    mcp_segment = _build_mcp_prompt_segment()
    system_prompt = (
        "You are an expert Python data debugging engineer. You will be given the original "
        "user prompt, the failing Python code block, the exact execution traceback/error, "
        "and the dataset schema. Your task is to identify and correct the error in the Python code.\n\n"
        "Execution Framework Rules:\n"
        "- The DataFrame is pre-loaded as global variable `df`. Do NOT mock, download, or re-read data files.\n"
        "- Available libraries: pandas (as pd), numpy (as np), matplotlib.pyplot (as plt)\n"
        "- Do NOT use scipy, seaborn (sns), plotly, or any other external libraries. Stick exclusively to pandas, numpy, and matplotlib.\n"
        "- For statistical calculations (e.g. regressions, curve fitting, trend lines, statistical indices, correlations), write them using numpy (e.g. np.polyfit, np.cov, np.corrcoef) or pandas (e.g. df.corr, df.describe, df.cov). This ensures 100% Android mobile compatibility.\n"
        "- For plotting, format with clean parameters and always call plt.tight_layout() before completion.\n"
        "- For plotting, check data dimensions before passing labels (e.g. tick_labels or labels).\n"
        "- Assign any critical table, subset metrics, or computation text to a local variable named `result`.\n"
        "- Ensure your generated code parses correctly, has valid indentation, handles NaNs appropriately, and fully complies with sandbox AST whitelisting rules.\n"
        "- Return only functional Python code. No introductory remarks, conversational wrappers, or markdown text."
        f"{mcp_segment}\n\n"
        f"Complete Dataset Metric Schema:\n{json.dumps(schema_json, default=str)}"
    )

    user_content = (
        f"Original Request: {prompt}\n\n"
        f"Failing Python Code:\n```python\n{bad_code}\n```\n\n"
        f"Execution Traceback/Error:\n{error_message}\n\n"
        "Please debug the code, fix the issue completely, and return ONLY the corrected, whitelisted, executable python block."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        data = await _call_gateway(TASK_CODE, messages)
        content = _extract_content(data)
        code = _extract_block_by_pattern(content, is_json=False)
        if not code.strip():
            logger.error("Corrected code generation returned empty payload.")
        return code
    except Exception as e:
        logger.error("Corrected code generation failed: %s", e)
        return ""


async def plan_next_step(
    schema_json: dict,
    initial_description: str,
    analysis_history: list[dict],
) -> dict:
    """Autopilot planner: given all previous analysis results, decide the next step.

    Returns:
        {"prompt": "...", "is_complete": False, "reason": "..."}
        or {"prompt": "", "is_complete": True, "reason": "Analysis is comprehensive."}
    """
    mcp_segment = _build_mcp_prompt_segment()

    history_summary = ""
    for i, entry in enumerate(analysis_history):
        status = "SUCCESS" if entry.get("success") else "FAILED"
        history_summary += (
            f"\n--- Step {i + 1} [{status}] ---\n"
            f"Prompt: {entry.get('prompt', '')}\n"
            f"Code: {entry.get('code', '')[:300]}\n"
            f"Result: {str(entry.get('result', ''))[:200]}\n"
            f"Insight: {entry.get('description', '')[:200]}\n"
        )
        if entry.get("error"):
            history_summary += f"Error: {entry.get('error')[:200]}\n"

    system_prompt = (
        "You are an autonomous data analysis agent. Your job is to decide the NEXT analysis step "
        "or determine that analysis is COMPLETE.\n\n"
        "Review the dataset schema and ALL previous analysis results. Then decide:\n"
        "1. If the analysis is already comprehensive (covered distributions, correlations, "
        "anomalies, key patterns, missing data, categorical breakdowns), return is_complete=true.\n"
        "2. Otherwise, return the NEXT specific analysis prompt to execute.\n\n"
        "Rules:\n"
        "- Do NOT repeat any previous analysis step.\n"
        "- Prioritize high-value analyses: correlations, distributions, outliers, trends, "
        "categorical breakdowns, missing data patterns, statistical summaries.\n"
        "- Be specific: the prompt must be a full instruction for pandas/matplotlib code generation.\n"
        f"{mcp_segment}\n"
        "Return ONLY a valid JSON object with these keys:\n"
        '- "prompt": the next analysis instruction (empty string if complete)\n'
        '- "is_complete": boolean\n'
        '- "reason": brief explanation of your decision\n'
        "No markdown, no code fences, no conversational text."
    )

    user_content = (
        f"Dataset Schema:\n{json.dumps(schema_json, default=str)}\n\n"
        f"Dataset Overview: {initial_description}\n\n"
        f"Analysis History (all previous steps):\n{history_summary}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        data = await _call_gateway(TASK_CODE, messages)
        content = _extract_content(data)
        cleaned = _extract_block_by_pattern(content, is_json=True)
        result = json.loads(cleaned)
        if isinstance(result, dict) and "prompt" in result and "is_complete" in result:
            return result
        return {
            "prompt": "",
            "is_complete": True,
            "reason": "Planner returned invalid format.",
        }
    except Exception as e:
        logger.error("Plan next step failed: %s", e)
        return {"prompt": "", "is_complete": True, "reason": f"Planner error: {e}"}


async def interpret(result_data: dict) -> str:
    """Send execution metrics to interpret route to fetch clean insight text."""
    system_prompt = (
        "You are a stellar data presentation assistant. Given computed numerical statistics "
        "and stdout print records, write a direct, highly cohesive interpretation. "
        "State patterns explicitly, quote exact figures, and highlight discoveries. "
        "Do NOT use any markdown (no bold, no italics, no bullet points, no headers). "
        "Write strictly as plain text, limited to at most 2 to 3 sentences."
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
        return "Analysis complete. Review workspace metrics for localized attributes."


async def analyze_image_for_data(
    image_bytes: bytes, mime_type: str, schema_json: dict
) -> str:
    """Eye + Code combo: extract metadata details from graphic and pipe straight to generator."""
    description = await analyze_image(image_bytes, mime_type)

    prompt = (
        f"The user uploaded an image attachment. Context extracted via vision system:\n\n"
        f"{description}\n\n"
        f"Correlate this visibility context against the loaded dataset variables and compile analytical code."
    )

    return await generate_code(prompt, schema_json)


async def generate_form_schema(prompt: str) -> dict | None:
    """Generate high-fidelity research forms with comprehensive structural depth."""
    system_prompt = (
        "You are an expert research survey designer and form builder AI. "
        "Your job is to generate COMPREHENSIVE, THOROUGH, RESEARCH-GRADE forms. "
        "Do NOT produce minimal or skeleton forms — think deeply about every angle of the topic.\n\n"
        "FIELD GENERATION RULES:\n"
        "- Generate 12 to 25 fields — NEVER fewer than 12\n"
        "- Start with demographics: age range, gender, education, region/location\n"
        "- Cover the topic from multiple angles: frequency, intensity, perception, attitude, experience, knowledge\n"
        "- Use select with Likert options (Strongly Agree/Agree/Neutral/Disagree/Strongly Disagree) for attitude questions\n"
        "- Use select with frequency options (Daily/Weekly/Monthly/Rarely/Never) for behavior questions\n"
        "- Use radio for mutually exclusive categorical choices\n"
        "- Use checkbox when multiple answers are valid\n"
        "- Include at least 2 textarea fields for open-ended qualitative responses\n"
        "- End with an open comments/anything-else textarea\n\n"
        "OUTPUT — return ONLY a raw JSON object, no markdown fences, no explanation:\n"
        '{"title":"...","description":"...","fields":[{"name":"snake_case","label":"Display label",'
        '"type":"text|textarea|number|email|select|radio|checkbox|date|phone|url|rating",'
        '"required":true,"options":["A","B"]}]}'
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        data = await _call_gateway(TASK_SUGGEST, messages)
        content = _extract_content(data)
        cleaned = _extract_block_by_pattern(content, is_json=True)
        return json.loads(cleaned)
    except Exception as e:
        logger.error("AI form gen failed: %s", e)
        return None


# ── Private helpers ─────────────────────────────────────────────────


async def _call_gateway(task_type: str, messages: list[dict]) -> dict:
    """Make a non-streaming POST to the gateway with retry and expanded processing thresholds."""
    payload = {
        "task_type": task_type,
        "stream": False,
        "messages": messages,
    }
    timeout = _TIMEOUTS.get(task_type, 20.0)

    resp = await request_with_retry(
        "POST",
        API_CHAT_ENDPOINT,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


async def _call_gateway_raw(payload: dict, timeout: float = 15.0) -> dict:
    """Make a raw POST to the gateway with active connection parameters."""
    resp = await request_with_retry(
        "POST",
        API_CHAT_ENDPOINT,
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def _extract_content(data: dict) -> str:
    """Extract assistant payload content while handling thinking steps safely."""
    try:
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "") or ""
            content = _strip_thinking(content)
            return content.strip()
    except (IndexError, KeyError, TypeError):
        pass
    return ""


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> reasoning blocks using efficient pre-compiled matching."""
    return _THINK_RE.sub("", text).strip()


def _extract_block_by_pattern(text: str, is_json: bool = False) -> str:
    """Uses advanced Regex pattern matching to pull code arrays safely.

    This replaces brittle index slicing and stops chat text wrappers from causing JSON parsing crashes.
    """
    cleaned = _strip_thinking(text)

    if is_json:
        # Look for target JSON block explicitly
        match = _JSON_BLOCK_RE.search(cleaned)
        if match:
            return match.group(1).strip()
    else:
        # Look for target Python block explicitly
        match = _PYTHON_BLOCK_RE.search(cleaned)
        if match:
            return match.group(1).strip()

    # Fallback to any generic backtick structure if targeted filters miss
    generic_match = _GENERIC_BLOCK_RE.search(cleaned)
    if generic_match:
        return generic_match.group(1).strip()

    # Final defense: return raw content stripped of block boundaries
    for trim_target in ["```python", "```json", "```"]:
        if cleaned.lower().startswith(trim_target):
            cleaned = cleaned[len(trim_target) :]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    return cleaned.strip()


def fallback_suggestions() -> list[dict]:
    """Return an expanded suite of safe fallbacks if remote channels are offline."""
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
        {
            "label": "Missing Values Audit",
            "icon": "🔍",
            "prompt": "Calculate percent of missing values in each column and render as a bar plot.",
        },
        {
            "label": "Value Counts Breakdown",
            "icon": "🗂",
            "prompt": "Identify categorical columns and show value distribution breakdown profiles.",
        },
    ]
