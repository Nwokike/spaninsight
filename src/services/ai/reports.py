"""AI report generation and editing."""

from __future__ import annotations

import json
import logging
from core.constants import TASK_SUGGEST
from .client import call_gateway, extract_content, extract_block_by_pattern

logger = logging.getLogger(__name__)


async def arrange_report(blocks: list[dict], dataset_name: str = "") -> dict | None:
    """AI auto-arranges report blocks into optimal order with polished descriptions."""
    system_prompt = (
        "You are an expert data report editor. Given analysis blocks, arrange them into "
        "a cohesive professional report.\n\n"
        "RULES:\n"
        "- Reorder blocks in logical flow (overview → distributions → correlations → anomalies → conclusions)\n"
        "- Generate a concise report title and 1-2 sentence description\n"
        "- Lightly polish each description for clarity. Do NOT change meaning or delete blocks\n"
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
        cleaned = extract_block_by_pattern(content, is_json=True)
        result = json.loads(cleaned)
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
        "- You may reorder blocks, edit titles and descriptions\n"
        "- You MUST NOT delete any blocks — return the same count\n"
        "- You MUST NOT change underlying data or metrics\n\n"
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
        cleaned = extract_block_by_pattern(content, is_json=True)
        result = json.loads(cleaned)
        if isinstance(result, dict) and "blocks" in result:
            logger.info("AI edited report: %d blocks", len(result["blocks"]))
            return result
        return None
    except Exception as e:
        logger.error("Edit report with AI failed: %s", e)
        return None
