"""Core AI data analysis, generation, and orchestration."""

from __future__ import annotations

import json
import logging
import re

from core.constants import TASK_SUGGEST, TASK_INTERPRET, TASK_CODE
from .client import call_gateway, extract_content, extract_block_by_pattern
from .vision import analyze_image

logger = logging.getLogger(__name__)


async def describe_dataset(schema_json: dict) -> str:
    """Block 0 describe: AI reads the schema and describes the dataset."""
    system_prompt = (
        "You are an expert data science director. Given a comprehensive dataset schema "
        "with structural details and distribution statistics, provide a professional, "
        "highly concise overview of what the data signifies and the macro domains it represents. "
        "Do NOT use any markdown (no bold, no italics, no bullet points, no headers). "
        "Write strictly as clear, plain-text prose, limited to at most 2 to 3 sentences."
    )
    ai_schema = dict(schema_json)
    ai_schema.pop("head", None)
    ai_schema.pop("tail", None)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(ai_schema, default=str)},
    ]
    try:
        data = await call_gateway(TASK_SUGGEST, messages)
        desc = extract_content(data)
        if desc:
            logger.info("Block 0 describe: %s", desc[:80])
            return desc
        return "Dataset loaded successfully."
    except Exception as e:
        logger.error("Describe dataset failed: %s", e)
        return "Dataset loaded. AI description unavailable."


async def describe_result(initial_description: str, latest_result: dict) -> str:
    """Block N describe: AI describes what a specific analysis result shows."""
    system_prompt = (
        "You are an expert data analyst. Describe what this specific data analysis "
        "execution result establishes. Interpret anomalies, specific distributions, exact "
        "numerical indices, and structural trends. "
        "Do NOT use any markdown (no bold, no italics, no bullet points, no headers). "
        "Write strictly as clear, plain-text analytical findings, limited to at most 2 to 3 sentences."
    )
    result_text = (
        f"Dataset: {initial_description}\n\n"
        f"Analysis Prompt: {latest_result.get('prompt', '')}\n"
        f"Executed Code:\n{latest_result.get('code', '')}\n\n"
        f"Standard Output Logs:\n{latest_result.get('stdout', '')}\n"
        f"Returned Value String:\n{latest_result.get('result', '')}"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": result_text},
    ]
    try:
        data = await call_gateway(TASK_INTERPRET, messages)
        content = extract_content(data)
        if content:
            logger.info("Block N describe: %s", content[:80])
            return content.strip()
        return "Analysis completed."
    except Exception as e:
        logger.error("Describe result failed: %s", e)
        return "Analysis completed."


async def suggest(
    schema_json: dict,
    initial_description: str = "",
    latest_result: dict | None = None,
    analysis_context: str = "",
) -> list[dict]:
    """Context-aware suggestions without cost-cutting limits."""
    # MODIFIED: Reduced from 5-8 to exactly 3 suggestions to drastically reduce generation time.
    system_prompt = (
        "You are an expert data intelligence consultant. Suggest a rich, multi-angle "
        "suite of exactly 3 distinct, deeply insightful data analysis tracks the user should perform next. "
        "Analyze trends, correlations, spatial maps, pivot metrics, and exploratory profiles. Do NOT repeat previous steps.\n\n"
        "CRITICAL EXECUTION CONSTRAINTS:\n"
        "- The execution environment supports: pandas, numpy, matplotlib.pyplot, math, datetime, statistics (Python standard library), shapely, jq, and pendulum.\n"
        "- The environment DOES NOT HAVE: seaborn, scipy, scikit-learn (sklearn), statsmodels, plotly, or pingouin.\n"
        "- Any visual suggestion must be plotting-compatible with MATPLOTLIB ONLY (do NOT suggest seaborn, plotly, etc.).\n"
        "- You are fully free to suggest and combine any calculations, spatial GIS operations, time-series shifts, database queries, or mathematical/statistical operations as long as they rely solely on the allowed whitelisted libraries.\n\n"
        "Return exclusively a valid, raw JSON array of objects with zero conversational wrappers. "
        "Each object must contain EXACTLY these keys:\n"
        '- "label": concise descriptive title (max 5 words)\n'
        '- "icon": "emoji" (always double-quoted emoji character)\n'
        '- "prompt": full structural instruction used to generate the required execution block\n'
        "Do not include code fences, preamble, or conversational notes outside the JSON array."
    )

    ai_schema = dict(schema_json)
    ai_schema.pop("head", None)
    ai_schema.pop("tail", None)
    context_parts = [json.dumps(ai_schema, default=str)]

    if initial_description:
        context_parts.append(f"\nDataset Overview: {initial_description}")

    if analysis_context:
        # MODIFIED: Truncate history to the last 2000 characters.
        # This prevents the prompt from bloating as the analysis session gets longer.
        truncated_history = (
            analysis_context[-2000:]
            if len(analysis_context) > 2000
            else analysis_context
        )
        context_parts.append(
            f"\nAnalysis History (do NOT repeat):\n...{truncated_history}"
        )
    elif latest_result:
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
        data = await call_gateway(TASK_SUGGEST, messages)
        content = extract_content(data)
        cleaned = extract_block_by_pattern(content, is_json=True)
        cleaned = re.sub(r'"icon"\s*:\s*([^"\s,{}]+)', r'"icon": "\1"', cleaned)
        suggestions = json.loads(cleaned)
        if isinstance(suggestions, list):
            return suggestions
        return []
    except Exception as e:
        logger.error("Suggest failed: %s", e)
        return fallback_suggestions()


async def generate_code(
    prompt: str, schema_json: dict, analysis_context: str = ""
) -> str:
    """Send prompt to code route using full uncut dataset schema statistics."""
    context_section = ""
    if analysis_context:
        context_section = f"\n\nPrevious Analysis Context (do NOT repeat these):\n{analysis_context}\n"

    system_prompt = (
        "You are an expert Python core data engineer. Generate optimal, safe Python "
        "code blocks to analyze the loaded DataFrame `df` according to the user's explicit request.\n\n"
        "CRITICAL — ONLY these standard/native libraries are available:\n"
        "  1. pandas (import as pd)\n"
        "  2. numpy  (import as np)\n"
        "  3. matplotlib.pyplot (import as plt)\n"
        "  4. math and datetime\n"
        "  5. statistics (Python standard library)\n"
        "  6. shapely (advanced geographic and vector computational geometry)\n"
        "  7. jq (JSON slicing and cleaning)\n"
        "  8. pendulum (advanced datetime parsing and manipulations)\n\n"
        "STRICTLY FORBIDDEN — do NOT import or use ANY of these (they will cause execution failure):\n"
        "  seaborn, sns, scipy, sklearn, statsmodels, plotly, pingouin, lifelines, any other non-whitelisted library.\n"
        "Execution Framework Rules:\n"
        "- The DataFrame is pre-loaded as global variable `df`.\n"
        "- Use modern Pandas 2.0+ Copy-on-Write syntax.\n"
        "- The environment uses NumPy 2.0+.\n"
        "- IMPORTANT: Always use `.dropna()` or `.fillna()` before performing algebraic, matrix, or statistical operations to prevent errors.\n"
        "- To select object/string columns with `select_dtypes`, NEVER pass 'object' alone (which triggers a deprecation warning). Instead, explicitly include 'str' as well: `select_dtypes(include=['object', 'str'])` or `select_dtypes(include=['object', 'string'])`.\n"
        "- You are fully free to write any classes, loops, custom calculations, statistics, or spatial algorithms. Build any advanced analysis directly using the allowed whitelisted modules.\n"
        "- For plotting, ALWAYS create a figure explicitly using plt.figure() or plt.subplots().\n"
        "- Assign any critical table, subset metrics, or computation text to a local variable named `result`.\n"
        "- Return only functional Python code. No introductory remarks.\n\n"
        f"Complete Dataset Metric Schema:\n{json.dumps(schema_json, default=str)}"
        f"{context_section}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        data = await call_gateway(TASK_CODE, messages)
        content = extract_content(data)
        code = extract_block_by_pattern(content, is_json=False)
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
    """Send failing code and traceback to generate corrected Python code."""
    system_prompt = (
        "You are an expert Python data debugging engineer. Correct the failing Python code block.\n\n"
        "CRITICAL — ONLY these standard/native libraries are available:\n"
        "  1. pandas (import as pd)\n"
        "  2. numpy  (import as np)\n"
        "  3. matplotlib.pyplot (import as plt)\n"
        "  4. math and datetime\n"
        "  5. statistics (Python standard library)\n"
        "  6. shapely (advanced geographic and vector computational geometry)\n"
        "  7. jq (JSON slicing and cleaning)\n"
        "  8. pendulum (advanced datetime parsing and manipulations)\n\n"
        "STRICTLY FORBIDDEN — do NOT import or use ANY of these (they will cause execution failure):\n"
        "  seaborn, sns, scipy, sklearn, statsmodels, plotly, pingouin, lifelines, any other non-whitelisted library.\n"
        "Execution Framework Rules:\n"
        "- The DataFrame is pre-loaded as global variable `df`.\n"
        "- Use modern Pandas 2.0+ Copy-on-Write syntax.\n"
        "- The environment uses NumPy 2.0+.\n"
        "- IMPORTANT: Always use `.dropna()` or `.fillna()` before performing algebraic, matrix, or statistical operations to prevent errors.\n"
        "- To select object/string columns with `select_dtypes`, NEVER pass 'object' alone (which triggers a deprecation warning). Instead, explicitly include 'str' as well: `select_dtypes(include=['object', 'str'])` or `select_dtypes(include=['object', 'string'])`.\n"
        "- You are fully free to write any classes, loops, custom calculations, statistics, or spatial algorithms. Build any advanced analysis directly using the allowed whitelisted modules.\n"
        "- For plotting, ALWAYS create a figure explicitly using plt.figure() or plt.subplots().\n"
        "- Assign any critical table, subset metrics, or computation text to a local variable named `result`.\n"
        "- Return only functional Python code. No introductory remarks.\n\n"
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
        data = await call_gateway(TASK_CODE, messages)
        content = extract_content(data)
        code = extract_block_by_pattern(content, is_json=False)
        return code
    except Exception as e:
        logger.error("Corrected code generation failed: %s", e)
        return ""


async def plan_next_step(
    schema_json: dict, initial_description: str, analysis_history: list[dict]
) -> dict:
    """Autopilot planner: given all previous analysis results, decide the next step."""
    history_lines = []
    for i, entry in enumerate(analysis_history):
        status = "✓" if entry.get("success") else "✗"
        prompt = entry.get("prompt", "")[:80]
        desc = entry.get("description", "")[:100]
        history_lines.append(f"  {i + 1}. [{status}] {prompt} → {desc}")

    history_summary = "\n".join(history_lines) if history_lines else "No steps yet."

    system_prompt = (
        "You are an autonomous data analysis agent. Your job is to decide the NEXT analysis step.\n\n"
        "CRITICAL EXECUTION CONSTRAINTS:\n"
        "- The execution environment supports: pandas, numpy, matplotlib.pyplot, math, datetime, statistics (Python standard library), shapely, jq, and pendulum.\n"
        "- The environment DOES NOT HAVE: seaborn, scipy, scikit-learn (sklearn), statsmodels, plotly, or pingouin.\n"
        "- Any analysis track you decide on must be fully executable using only these allowed whitelisted libraries. Plan any statistical, spatial, or datetime analyses standardly using their provided capabilities.\n\n"
        "Return ONLY a valid JSON object with these keys:\n"
        '- "prompt": the next analysis instruction (empty string if complete)\n'
        '- "is_complete": boolean\n'
        '- "reason": brief explanation of your decision\n'
    )

    user_content = (
        f"Dataset Schema:\n{json.dumps(schema_json, default=str)}\n\n"
        f"Dataset Overview: {initial_description}\n\n"
        f"Completed Steps ({len(analysis_history)} total):\n{history_summary}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        data = await call_gateway(TASK_CODE, messages)
        content = extract_content(data)
        cleaned = extract_block_by_pattern(content, is_json=True)
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
        "You are a stellar data presentation assistant. Write a direct interpretation of the stats. "
        "Write strictly as plain text, limited to at most 2 to 3 sentences."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(result_data, default=str)},
    ]
    try:
        data = await call_gateway(TASK_INTERPRET, messages)
        return extract_content(data)
    except Exception as e:
        logger.error("Interpret failed: %s", e)
        return "Analysis complete. Review workspace metrics."


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


def fallback_suggestions() -> list[dict]:
    """Return an expanded suite of safe fallbacks if remote channels are offline."""
    # MODIFIED: Reduced to 3 to match the new lightweight structure
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
            "label": "Missing Values Audit",
            "icon": "🔍",
            "prompt": "Calculate percent of missing values in each column and render as a bar plot.",
        },
    ]
