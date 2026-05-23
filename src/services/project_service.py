"""Project management service — collaboration, creation, join, and sync.

Groups all analyses, forms, and reports under project scopes.
Synchronizes project state with D1/R2 gateway.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import logging
import uuid


import flet as ft

from core.constants import API_BASE_URL
from core.state import state
from services.api_client import get_client, request_with_retry
from services.bip39_words import BIP39_WORDS

logger = logging.getLogger(__name__)

# Key under which all local projects dict is stored in StorageService
STORAGE_PROJECTS = "spaninsight_projects"
STORAGE_ACTIVE_PROJECT_ID = "spaninsight_active_project_id"


class ProjectService:
    def __init__(self, page: ft.Page, storage):
        self._page = page
        self._storage = storage

    async def initialize_projects(self) -> str:
        """Load projects from storage or create a default one. Returns active_project_id."""
        try:
            # 1. Load active project ID
            active_id = await self._storage.get(STORAGE_ACTIVE_PROJECT_ID)

            # 2. Load all local projects
            raw_projects = await self._storage.get(STORAGE_PROJECTS)
            projects = json.loads(raw_projects) if raw_projects else {}

            state.user_projects = projects

            if not projects:
                # No projects exist, create default workspace
                logger.info("No projects found. Generating default workspace...")
                default_proj = await self.create_local_project("My Workspace")
                active_id = default_proj["id"]

                # Proactively try to register default project in D1 gateway in the background
                import asyncio

                asyncio.create_task(self.sync_project(active_id))

            if not active_id or active_id not in state.user_projects:
                active_id = next(iter(state.user_projects.keys()))

            state.active_project_id = active_id
            await self._storage.set(STORAGE_ACTIVE_PROJECT_ID, active_id)
            return active_id

        except Exception as e:
            logger.error("Failed to initialize projects: %s", e)
            return ""

    async def create_local_project(self, title: str, description: str = "") -> dict:
        """Create a new offline-ready project locally with a recovery phrase."""
        proj_uuid = str(uuid.uuid4())
        phrase = self.uuid_to_phrase(proj_uuid)
        phrase_hash = self.phrase_to_hash(phrase)

        # Temp local ID until registered/synced with server
        temp_id = "loc_" + proj_uuid[:8]

        project = {
            "id": temp_id,
            "title": title,
            "description": description,
            "phrase": phrase,
            "phrase_hash": phrase_hash,
            "current_df_name": "",
            "current_file_path": "",
            "analysis_blocks": [],
            "user_reports": [],
            "forms": [],
            "synced_at": 0,
        }

        state.user_projects[temp_id] = project
        await self._persist_local_projects()
        return project

    async def create_project(self, title: str, description: str = "") -> dict:
        """Register a new project on the Cloudflare gateway."""
        # 1. Setup local project state
        proj = await self.create_local_project(title, description)
        temp_id = proj["id"]

        # 2. Package sync JSON
        project_json = self._serialize_project(proj)

        payload = {
            "phrase_hash": proj["phrase_hash"],
            "title": proj["title"],
            "description": proj["description"],
            "project_json": project_json,
        }

        try:
            resp = await request_with_retry(
                "POST",
                f"{API_BASE_URL}/projects",
                json=payload,
                timeout=10.0,
            )
            if resp.status_code == 201:
                data = resp.json()
                server_id = data["id"]

                # Replace local temporary ID with server generated 6-digit PIN ID
                state.user_projects.pop(temp_id, None)
                proj["id"] = server_id
                proj["synced_at"] = datetime.datetime.now().timestamp()
                state.user_projects[server_id] = proj

                state.active_project_id = server_id
                await self._storage.set(STORAGE_ACTIVE_PROJECT_ID, server_id)
                await self._persist_local_projects()
                logger.info("Project registered in gateway. PIN: %s", server_id)
                return proj
        except Exception as e:
            logger.warning(
                "Could not register project in gateway: %s. Keeping local.", e
            )

        # Fallback: Set active locally
        state.active_project_id = temp_id
        await self._storage.set(STORAGE_ACTIVE_PROJECT_ID, temp_id)
        return proj

    async def sync_project(self, project_id: str) -> bool:
        """Upload local project state modifications to gateway."""
        proj = state.user_projects.get(project_id)
        if not proj:
            return False

        # If project is still local, attempt to register it
        if project_id.startswith("loc_"):
            logger.info("Attempting to register local project '%s'...", proj["title"])
            project_json = self._serialize_project(proj)
            payload = {
                "phrase_hash": proj["phrase_hash"],
                "title": proj["title"],
                "description": proj["description"],
                "project_json": project_json,
            }
            try:
                resp = await request_with_retry(
                    "POST",
                    f"{API_BASE_URL}/projects",
                    json=payload,
                    timeout=10.0,
                )
                if resp.status_code == 201:
                    data = resp.json()
                    server_id = data["id"]

                    state.user_projects.pop(project_id, None)
                    proj["id"] = server_id
                    proj["synced_at"] = datetime.datetime.now().timestamp()
                    state.user_projects[server_id] = proj

                    if state.active_project_id == project_id:
                        state.active_project_id = server_id
                        await self._storage.set(STORAGE_ACTIVE_PROJECT_ID, server_id)
                    await self._persist_local_projects()
                    logger.info(
                        "Local project successfully registered. PIN: %s", server_id
                    )
                    return True
            except Exception as e:
                logger.warning("Could not register local project in gateway: %s", e)
            return False

        project_json = self._serialize_project(proj)
        payload = {
            "title": proj["title"],
            "description": proj["description"],
            "project_json": project_json,
        }

        try:
            resp = await request_with_retry(
                "POST",
                f"{API_BASE_URL}/projects/{project_id}/sync",
                json=payload,
                timeout=10.0,
            )
            if resp.status_code == 200:
                proj["synced_at"] = datetime.datetime.now().timestamp()
                await self._persist_local_projects()
                logger.info(
                    "Project '%s' successfully synced to Cloudflare gateway.",
                    proj["title"],
                )
                return True
        except Exception as e:
            logger.warning("Project sync failed: %s", e)
        return False

    async def join_project_by_pin(self, pin: str) -> dict | None:
        """Join a collaborative project using its 6-digit Share PIN."""
        try:
            client = get_client()
            resp = await client.get(
                f"{API_BASE_URL}/projects/{pin}",
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                proj_data = self._deserialize_project(
                    data["id"], data["title"], data["description"], data["project_json"]
                )

                # Retrieve phrase hash
                proj_data["phrase_hash"] = data.get("phrase_hash", "")
                proj_data["synced_at"] = datetime.datetime.now().timestamp()

                state.user_projects[data["id"]] = proj_data
                state.active_project_id = data["id"]
                await self._storage.set(STORAGE_ACTIVE_PROJECT_ID, data["id"])
                await self._persist_local_projects()

                logger.info("Successfully joined project '%s' by PIN", data["title"])
                return proj_data
            else:
                logger.warning("Join project failed: HTTP %d", resp.status_code)
        except Exception as e:
            logger.error("Failed to join project: %s", e)
        return None

    async def join_project_by_phrase(self, phrase: str) -> dict | None:
        """Join a collaborative project using its 12-word seed phrase."""
        phrase = phrase.strip().lower()
        phrase_hash = self.phrase_to_hash(phrase)

        try:
            client = get_client()
            resp = await client.get(
                f"{API_BASE_URL}/projects/restore",
                params={"phrase_hash": phrase_hash},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                proj_data = self._deserialize_project(
                    data["id"], data["title"], data["description"], data["project_json"]
                )
                proj_data["phrase"] = phrase
                proj_data["phrase_hash"] = phrase_hash
                proj_data["synced_at"] = datetime.datetime.now().timestamp()

                state.user_projects[data["id"]] = proj_data
                state.active_project_id = data["id"]
                await self._storage.set(STORAGE_ACTIVE_PROJECT_ID, data["id"])
                await self._persist_local_projects()

                logger.info("Successfully joined project '%s' by phrase", data["title"])
                return proj_data
            else:
                logger.warning(
                    "Join project by phrase failed: HTTP %d", resp.status_code
                )
        except Exception as e:
            logger.error("Failed to restore project by phrase: %s", e)
        return None

    async def pull_project(self, project_id: str) -> bool | str:
        """Fetch remote project details to synchronize.

        Returns:
            "local"   - project is offline-only (not registered in cloud)
            "deleted" - project has been deleted from gateway D1
            True      - successfully pulled and updated newer changes
            False     - offline, connection timeout, or no new updates
        """
        if project_id.startswith("loc_"):
            return "local"

        proj = state.user_projects.get(project_id)
        if not proj:
            return False

        try:
            client = get_client()
            resp = await client.get(
                f"{API_BASE_URL}/projects/{project_id}",
                timeout=8.0,
            )
            if resp.status_code == 200:
                data = resp.json()

                # Parse server update time
                server_updated_str = data.get("updated_at", "")
                server_ts = self._parse_gateway_datetime(server_updated_str)
                local_synced_ts = proj.get("synced_at", 0)

                # Only overwrite local if server contains a newer revision
                if server_ts > local_synced_ts:
                    logger.info(
                        "Server version is newer for project '%s'. Merging changes...",
                        proj["title"],
                    )
                    server_proj = self._deserialize_project(
                        data["id"],
                        data["title"],
                        data["description"],
                        data["project_json"],
                    )

                    # RETAIN device-specific local raw dataset paths!
                    server_proj["current_file_path"] = proj.get("current_file_path", "")
                    server_proj["current_df_name"] = proj.get("current_df_name", "")
                    server_proj["synced_at"] = datetime.datetime.now().timestamp()

                    state.user_projects[project_id] = server_proj
                    await self._persist_local_projects()
                    return True
                return False

            elif resp.status_code == 404:
                logger.warning(
                    "Project %s not found on server (deleted on D1).", project_id
                )
                return "deleted"
        except Exception as e:
            logger.warning("Failed to pull project %s: %s", project_id, e)
        return False

    def _parse_gateway_datetime(self, dt_str: str) -> float:
        """Robust parse helper for SQLite YYYY-MM-DD HH:MM:SS or standard ISO dates."""
        if not dt_str:
            return 0.0
        try:
            # ISO Format (e.g. 2026-05-23T14:15:30.000Z)
            cleaned = dt_str.replace("Z", "").split(".")[0]
            if "T" in cleaned:
                dt = datetime.datetime.fromisoformat(cleaned)
            else:
                # SQLite datetime('now') -> 2026-05-23 14:15:30
                dt = datetime.datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
            return dt.timestamp()
        except Exception:
            return 0.0

    async def rename_project(self, project_id: str, new_title: str) -> bool:
        """Rename active project locally and push changes to server."""
        proj = state.user_projects.get(project_id)
        if not proj:
            return False
        proj["title"] = new_title
        await self._persist_local_projects()

        # Sync changes to server
        return await self.sync_project(project_id)

    async def delete_project(self, project_id: str) -> bool:
        """Remove a project locally and trigger gateway purge."""
        state.user_projects.pop(project_id, None)
        await self._persist_local_projects()

        # Trigger cascade delete in D1
        if not project_id.startswith("loc_"):
            try:
                client = get_client()
                await client.delete(
                    f"{API_BASE_URL}/projects/{project_id}",
                    timeout=10.0,
                )
            except Exception as e:
                logger.warning("Delete project from gateway failed: %s", e)

        # Update active project reference if deleted project was active
        if state.active_project_id == project_id:
            if state.user_projects:
                state.active_project_id = next(iter(state.user_projects.keys()))
            else:
                await self.create_local_project("My Workspace")
                state.active_project_id = next(iter(state.user_projects.keys()))
            await self._storage.set(STORAGE_ACTIVE_PROJECT_ID, state.active_project_id)

        return True

    # ── Helpers ──────────────────────────────────────────────────────

    async def _persist_local_projects(self):
        """Write current user_projects cache to storage settings."""
        # Ensure we don't try to serialize bytes!
        safe_copy = {}
        for pid, p in state.user_projects.items():
            safe_copy[pid] = self._serialize_project(p)
        await self._storage.set(STORAGE_PROJECTS, json.dumps(safe_copy))

    def _serialize_project(self, proj: dict) -> dict:
        """Prepare project data dict for JSON serialization (encoding bytes)."""
        copied = json.loads(json.dumps(proj, default=str))

        # Custom serialize analysis_blocks: convert raw bytes figure_png to base64
        for b in copied.get("analysis_blocks", []):
            orig_block = next(
                (
                    ob
                    for ob in proj.get("analysis_blocks", [])
                    if ob.get("prompt") == b.get("prompt")
                ),
                None,
            )
            if orig_block and orig_block.get("figure_png"):
                b["figure_png_b64"] = base64.b64encode(orig_block["figure_png"]).decode(
                    "utf-8"
                )
            b.pop("figure_png", None)
            b.pop("figure", None)

        return copied

    def _deserialize_project(
        self, pid: str, title: str, description: str, project_json: dict | str
    ) -> dict:
        """Construct full local project dict from JSON details (decoding base64)."""
        if isinstance(project_json, str):
            meta = json.loads(project_json)
        else:
            meta = project_json

        # Custom deserialize analysis_blocks: decode base64 back to raw bytes
        for b in meta.get("analysis_blocks", []):
            b["figure"] = None
            if "id" not in b or not b["id"]:
                b["id"] = "blk_" + str(uuid.uuid4())[:8]
            if b.get("figure_png_b64"):
                b["figure_png"] = base64.b64decode(b["figure_png_b64"])
            else:
                b["figure_png"] = None

        return {
            "id": pid,
            "title": title,
            "description": description,
            "phrase": meta.get("phrase", ""),
            "phrase_hash": meta.get("phrase_hash", ""),
            "current_df_name": meta.get("current_df_name", ""),
            "current_file_path": meta.get("current_file_path", ""),
            "analysis_blocks": meta.get("analysis_blocks", []),
            "user_reports": meta.get("user_reports", []),
            "forms": meta.get("forms", []),
            "synced_at": meta.get("synced_at", 0),
        }

    def uuid_to_phrase(self, user_uuid: str) -> str:
        """Convert a 128-bit UUID integer to a 12-word recovery mnemonic."""
        u_int = uuid.UUID(user_uuid).int
        words = []
        temp_val = u_int
        for _ in range(12):
            idx = temp_val % 2048
            words.append(BIP39_WORDS[idx])
            temp_val //= 2048
        return " ".join(words)

    @staticmethod
    def phrase_to_hash(phrase: str) -> str:
        """SHA-256 hash of the recovery phrase."""
        return hashlib.sha256(phrase.strip().lower().encode()).hexdigest()[:32]
