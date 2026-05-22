"""Report management — local-first storage with R2 sharing.

Reports live entirely on-device in StorageService. R2 is only used
for ephemeral sharing (7-day auto-delete, renewable).
"""

from __future__ import annotations

import json
import logging
import random
import string
import time

from core.constants import API_BASE_URL, STORAGE_REPORTS
from services.api_client import request_with_retry

logger = logging.getLogger(__name__)


class ReportService:
    """Local-first report management with optional R2 sharing."""

    def __init__(self, storage):
        self._storage = storage

    async def _load_all(self) -> list[dict]:
        try:
            raw = await self._storage.get(STORAGE_REPORTS)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning("Failed to load reports: %s", e)
        return []

    async def _save_all(self, reports: list[dict]) -> None:
        try:
            await self._storage.set(STORAGE_REPORTS, json.dumps(reports, default=str))
        except Exception as e:
            logger.error("Failed to save reports: %s", e)

    async def list_reports(self) -> list[dict]:
        reports = await self._load_all()
        reports.sort(key=lambda r: r.get("updated_at", 0), reverse=True)
        return reports

    async def create_report(
        self, title: str, dataset_name: str, blocks: list[dict]
    ) -> dict:
        report = {
            "id": self._generate_id(),
            "title": title,
            "description": "",
            "is_arranged": False,
            "created_at": time.time(),
            "updated_at": time.time(),
            "dataset_name": dataset_name,
            "share_id": None,
            "share_url": None,
            "blocks": blocks,
        }
        reports = await self._load_all()
        reports.insert(0, report)
        await self._save_all(reports)
        logger.info(
            "Created report %s: %s (%d blocks)", report["id"], title, len(blocks)
        )
        return report

    async def get_report(self, report_id: str) -> dict | None:
        reports = await self._load_all()
        for r in reports:
            if r["id"] == report_id:
                return r
        return None

    async def update_report(self, report_id: str, updates: dict) -> bool:
        reports = await self._load_all()
        for r in reports:
            if r["id"] == report_id:
                r.update(updates)
                r["updated_at"] = time.time()
                await self._save_all(reports)
                return True
        return False

    async def delete_report(self, report_id: str) -> bool:
        reports = await self._load_all()
        original_len = len(reports)
        reports = [r for r in reports if r["id"] != report_id]
        if len(reports) < original_len:
            await self._save_all(reports)
            return True
        return False

    async def add_block_to_report(self, report_id: str, block: dict) -> bool:
        reports = await self._load_all()
        for r in reports:
            if r["id"] == report_id:
                r.setdefault("blocks", []).append(block)
                r["updated_at"] = time.time()
                await self._save_all(reports)
                return True
        return False

    async def share_report(self, report: dict, user_uuid: str) -> str | None:
        items = []
        for block in report.get("blocks", []):
            item = {
                "prompt": block.get("prompt", ""),
                "description": block.get("description", ""),
            }
            if block.get("figure_png_b64"):
                item["image_b64"] = block["figure_png_b64"]
            items.append(item)

        report_json = {
            "title": report.get("title", "Spaninsight Report"),
            "chart_count": len(items),
            "items": items,
        }

        try:
            resp = await request_with_retry(
                "POST",
                f"{API_BASE_URL}/reports",
                json={"user_uuid": user_uuid, "report_json": report_json},
                timeout=15.0,
            )
            if resp.status_code == 201:
                data = resp.json()
                share_id = data.get("id", "")
                share_url = data.get("url", "")
                reports = await self._load_all()
                for r in reports:
                    if r["id"] == report["id"]:
                        r["share_id"] = share_id
                        r["share_url"] = share_url
                        r["updated_at"] = time.time()
                        break
                await self._save_all(reports)
                return share_url
            return None
        except Exception as e:
            logger.error("Share report error: %s", e)
            return None

    async def renew_share(self, report_id: str) -> bool:
        report = await self.get_report(report_id)
        if not report or not report.get("share_id"):
            return False
        try:
            resp = await request_with_retry(
                "POST",
                f"{API_BASE_URL}/reports/{report['share_id']}/renew",
                json={},
                timeout=10.0,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error("Renew share error: %s", e)
            return False

    @staticmethod
    def _generate_id() -> str:
        chars = string.ascii_lowercase + string.digits
        return "rpt_" + "".join(random.choices(chars, k=8))
