"""Forms API client — CRUD operations against the D1-backed gateway.

Handles form creation, listing, response fetching, CSV download,
renewal, and deletion.

Audit fixes: Uses shared httpx client (C3), moved pandas import (M3).
"""

from __future__ import annotations

import logging

from core.constants import API_BASE_URL
from services.api_client import get_client, request_with_retry

logger = logging.getLogger(__name__)


async def create_form(
    user_uuid: str,
    title: str,
    description: str,
    schema_json: list[dict],
) -> dict | None:
    """Create a form via the gateway. Returns {id, url, expires_at} or None."""

    # Validate schema structure before sending
    if not isinstance(schema_json, list):
        logger.error("Form schema must be a list, got %s", type(schema_json).__name__)
        return None

    valid_types = {"text", "textarea", "number", "email", "select", "radio", "checkbox", "date", "phone", "url", "rating"}
    for i, field in enumerate(schema_json):
        if not isinstance(field, dict):
            logger.error("Field %d is not a dict", i)
            return None
        if "name" not in field or "label" not in field or "type" not in field:
            logger.error("Field %d missing required keys (name, label, type)", i)
            return None
        if field["type"] not in valid_types:
            logger.error("Field %d has invalid type: %s", i, field["type"])
            return None

    payload = {
        "user_uuid": user_uuid,
        "title": title,
        "description": description,
        "schema_json": schema_json,
    }
    try:
        resp = await request_with_retry(
            "POST",
            f"{API_BASE_URL}/forms",
            json=payload,
            timeout=10.0,
        )
        if resp.status_code == 201:
            data = resp.json()
            logger.info("Form created: %s → %s", data["id"], data["url"])
            return data
        logger.error(
            "Create form failed HTTP %d: %s", resp.status_code, resp.text[:200]
        )
        return None
    except Exception as e:
        logger.error("Create form error: %s", e)
        return None


async def list_forms(user_uuid: str) -> list[dict]:
    """Fetch all forms for a user. Returns list of form dicts."""
    try:
        client = get_client()
        resp = await client.get(
            f"{API_BASE_URL}/forms",
            params={"uuid": user_uuid},
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json().get("forms", [])
        return []
    except Exception as e:
        logger.error("List forms error: %s", e)
        return []


async def get_responses(form_id: str, user_uuid: str = "") -> dict:
    """Fetch all responses for a form. Returns {count, responses}."""
    try:
        client = get_client()
        params = {}
        if user_uuid:
            params["uuid"] = user_uuid
        resp = await client.get(
            f"{API_BASE_URL}/forms/{form_id}/responses",
            params=params,
            timeout=15.0,
        )
        if resp.status_code == 200:
            return resp.json()
        return {"count": 0, "responses": []}
    except Exception as e:
        logger.error("Get responses error: %s", e)
        return {"count": 0, "responses": []}


async def renew_form(form_id: str, user_uuid: str = "") -> str | None:
    """Extend form expiry by 7 days. Returns new expires_at or None."""
    try:
        resp = await request_with_retry(
            "POST",
            f"{API_BASE_URL}/forms/{form_id}/renew",
            json={"uuid": user_uuid} if user_uuid else None,
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json().get("expires_at")
        return None
    except Exception as e:
        logger.error("Renew form error: %s", e)
        return None


async def delete_form(form_id: str, user_uuid: str = "") -> bool:
    """Delete a form and all its responses."""
    try:
        client = get_client()
        resp = await client.request(
            "DELETE",
            f"{API_BASE_URL}/forms/{form_id}",
            json={"uuid": user_uuid} if user_uuid else None,
            timeout=10.0,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.error("Delete form error: %s", e)
        return False


def responses_to_csv_bytes(responses: list[dict]) -> bytes:
    """Convert a list of response dicts to CSV bytes for download.

    Each response has a 'data' dict with field values.
    """
    import pandas as pd
    if not responses:
        return b""

    rows = [r["data"] for r in responses]
    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode("utf-8")
