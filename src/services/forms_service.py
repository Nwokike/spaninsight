"""Forms API client — CRUD operations against the D1-backed gateway.

Handles form creation, listing, response fetching, CSV download,
renewal, and deletion.
"""

from __future__ import annotations

import logging

import httpx

from core.constants import API_BASE_URL, APP_SECRET, USER_AGENT

logger = logging.getLogger(__name__)

_HEADERS = {
    "X-App-Secret": APP_SECRET,
    "User-Agent": USER_AGENT,
    "Content-Type": "application/json",
}


async def create_form(
    user_uuid: str,
    title: str,
    description: str,
    schema_json: list[dict],
) -> dict | None:
    """Create a form via the gateway. Returns {id, url, expires_at} or None."""
    payload = {
        "user_uuid": user_uuid,
        "title": title,
        "description": description,
        "schema_json": schema_json,
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API_BASE_URL}/forms",
                headers=_HEADERS,
                json=payload,
                timeout=10.0,
            )
            if resp.status_code == 201:
                data = resp.json()
                logger.info("Form created: %s → %s", data["id"], data["url"])
                return data
            logger.error("Create form failed HTTP %d: %s", resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.error("Create form error: %s", e)
        return None


async def list_forms(user_uuid: str) -> list[dict]:
    """Fetch all forms for a user. Returns list of form dicts."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{API_BASE_URL}/forms",
                headers=_HEADERS,
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
        async with httpx.AsyncClient() as client:
            params = {}
            if user_uuid:
                params["uuid"] = user_uuid
            resp = await client.get(
                f"{API_BASE_URL}/forms/{form_id}/responses",
                headers=_HEADERS,
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
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API_BASE_URL}/forms/{form_id}/renew",
                headers=_HEADERS,
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
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                "DELETE",
                f"{API_BASE_URL}/forms/{form_id}",
                headers=_HEADERS,
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
