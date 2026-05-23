"""AI report generation and editing."""

from __future__ import annotations

import json
import logging
from core.constants import TASK_SUGGEST
from .client import call_gateway, extract_content, extract_block_by_pattern

logger = logging.getLogger(__name__)


def _parse_resilient_json(text: str) -> dict | None:
    """Robustly extract and parse a JSON object from raw LLM output."""
    import re
    from .client import strip_thinking

    cleaned = extract_block_by_pattern(text, is_json=True)
    cleaned = strip_thinking(cleaned)

    # Locate first { and last }
    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first != -1 and last != -1 and last >= first:
        cleaned = cleaned[first : last + 1]

    try:
        return json.loads(cleaned, strict=False)
    except Exception as e:
        logger.warning(
            "Standard strict=False JSON parsing failed: %s. Attempting custom repairs.",
            e,
        )
        # Attempt trailing comma cleanup and other standard JSON formatting issues
        try:
            # Strip trailing commas from object arrays
            repaired = re.sub(r",\s*([\]}])", r"\1", cleaned)
            return json.loads(repaired, strict=False)
        except Exception as ex:
            logger.error(
                "All JSON repair attempts failed. Original text length: %d. Error: %s",
                len(text),
                ex,
            )
            raise ex


async def arrange_report(blocks: list[dict], dataset_name: str = "") -> dict | None:
    """AI auto-arranges report blocks into optimal order with polished descriptions."""
    system_prompt = (
        "You are an expert data report editor. Given analysis blocks, arrange them into "
        "a cohesive professional report.\n\n"
        "RULES:\n"
        "- Reorder blocks in logical flow (overview → distributions → correlations → anomalies → conclusions)\n"
        "- Generate a concise, polished report title and a beautiful, consumer-friendly 1-2 sentence executive summary description (focused on business impact and overview of findings, avoiding raw technical/analytical descriptions)\n"
        "- IMPORTANT: Reformat the title/prompt of each block to be a beautiful, concise, and professional section header "
        "(e.g., 'Data Ingestion & Loading' instead of 'import necessary libraries and load the asset', "
        "'Missing Data Imputation' instead of 'clean the dataset, input missing values in age using the median'). "
        "Never leave a block title as a task instruction, python description, or raw question. "
        "Make it read like a premium executive slide title!\n"
        "- CRITICAL: You MUST NOT modify, edit, or touch the block-level descriptions at all! Return them exactly identical to how you received them in the input list so that the user's custom edits are fully preserved.\n"
        "- Return the SAME number of blocks you received\n\n"
        "OUTPUT — return ONLY raw JSON, no markdown fences:\n"
        '{"title":"...", "description":"...", "blocks":[{"prompt":"...", "description":"...", "original_index": 0}]}\n'
        "original_index = 0-based index in the input list."
    )

    blocks_summary = [
        {
            "index": i,
            "prompt": b.get("prompt", ""),
            "description": b.get("description", ""),
        }
        for i, b in enumerate(blocks)
    ]
    user_content = (
        f"Dataset: {dataset_name}\n\nBlocks:\n{json.dumps(blocks_summary, default=str)}"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        data = await call_gateway(TASK_SUGGEST, messages)
        content = extract_content(data)
        result = _parse_resilient_json(content)
        if isinstance(result, dict) and "blocks" in result:
            logger.info(
                "AI arranged report: %s (%d blocks)",
                result.get("title", ""),
                len(result["blocks"]),
            )
            return result
        return None
    except Exception as e:
        logger.error("Arrange report failed: %s", e)
        return None


async def edit_report_with_ai(
    current_blocks: list[dict],
    title: str,
    description: str,
    user_instruction: str,
) -> dict | None:
    """AI edits report based on user instruction (reorder, rephrase, etc.)."""
    system_prompt = (
        "You are an expert report editor. Apply the user's edit instruction to the report.\n\n"
        "RULES:\n"
        "- You may reorder blocks, edit report titles, and update the report-level description.\n"
        "- Generate a beautiful, concise report-level description as an executive summary of the findings (not analytical or technical, but focused on business impact and overview of findings).\n"
        "- You MUST NOT modify, edit, or touch any block-level descriptions unless the user's edit instruction explicitly requests it (e.g., 'rewrite the descriptions to be shorter', 'change description of block 2'). If not explicitly specified by the user, return all block-level descriptions exactly identical to how you received them in the input list.\n"
        "- You MUST NOT delete any blocks — return the same count\n"
        "- You MUST NOT change underlying data or metrics\n"
        "- IMPORTANT: Ensure all block titles/prompts are concise, professional section headers "
        "(e.g., 'Target Variable Correlation' instead of 'check correlation with target variable'). "
        "Never leave a block title as a task instruction, python description, or raw question.\n\n"
        "OUTPUT — return ONLY raw JSON, no markdown fences:\n"
        '{"title":"...", "description":"...", "blocks":[{"prompt":"...", "description":"...", "original_index": 0}]}\n'
        "original_index = 0-based index in the INPUT list."
    )

    blocks_summary = [
        {
            "index": i,
            "prompt": b.get("prompt", ""),
            "description": b.get("description", ""),
        }
        for i, b in enumerate(current_blocks)
    ]
    user_content = (
        f"Report Title: {title}\nDescription: {description}\n\n"
        f"Blocks:\n{json.dumps(blocks_summary, default=str)}\n\n"
        f"Edit Instruction: {user_instruction}"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        data = await call_gateway(TASK_SUGGEST, messages)
        content = extract_content(data)
        result = _parse_resilient_json(content)
        if isinstance(result, dict) and "blocks" in result:
            logger.info("AI edited report: %d blocks", len(result["blocks"]))
            return result
        return None
    except Exception as e:
        logger.error("Edit report with AI failed: %s", e)
        return None
