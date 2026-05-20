"""Settings view — UUID backup, credits, theme, pro tease."""

from __future__ import annotations

import logging

import flet as ft

from core import theme, tokens
from core.state import state
from core.constants import (
    STORAGE_THEME,
    STORAGE_UUID,
    STORAGE_CREDITS,
    STORAGE_BONUS_CREDITS,
    STORAGE_LAST_RESET,
    STORAGE_REFERRAL_CODE,
    STORAGE_MCP_SERVERS,
)
from core.styles import section_header, setting_tile
from components.brand_header import build_brand_header
from services.mcp_client import mcp_manager
import json
import asyncio

logger = logging.getLogger(__name__)


def build_settings_view(
    page: ft.Page,
    uuid_service,
    credit_service,
    storage=None,
) -> ft.View:
    """Build the Settings tab view."""

    def show_dialog(dialog):
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    async def close_dialog_helper(dialog):
        dialog.open = False
        page.update()
        await asyncio.sleep(0.1)
        if dialog in page.overlay:
            page.overlay.remove(dialog)
            page.update()

    async def on_copy_uuid(e):
        user_uuid = await uuid_service.get_uuid()
        if user_uuid:
            await page.clipboard.set(user_uuid)
            page.snack_bar = ft.SnackBar(
                content=ft.Text("UUID copied to clipboard"),
                duration=2000,
            )
            page.snack_bar.open = True
            page.update()

    async def on_copy_phrase(e):
        phrase = await uuid_service.get_backup_phrase()
        if phrase:
            await page.clipboard.set(phrase)
            page.snack_bar = ft.SnackBar(
                content=ft.Text("Backup phrase copied!"),
                duration=2000,
            )
            page.snack_bar.open = True
            page.update()

    async def on_theme_changed(e):
        mode = e.control.value
        if mode == "dark":
            page.theme_mode = ft.ThemeMode.DARK
        elif mode == "light":
            page.theme_mode = ft.ThemeMode.LIGHT
        else:
            page.theme_mode = ft.ThemeMode.SYSTEM
        state.theme_mode = page.theme_mode

        # Persist
        if storage:
            await storage.set(STORAGE_THEME, mode)

        page.update()

    async def on_clear_data(e):
        def close_dialog(confirmed):
            async def _close(ev):
                await close_dialog_helper(dialog)
                if confirmed and storage:
                    # Wipe ALL storage keys
                    for key in [
                        STORAGE_UUID,
                        STORAGE_THEME,
                        STORAGE_CREDITS,
                        STORAGE_BONUS_CREDITS,
                        STORAGE_LAST_RESET,
                        STORAGE_REFERRAL_CODE,
                        STORAGE_MCP_SERVERS,
                    ]:
                        try:
                            await storage.delete(key)
                        except Exception:
                            pass
                    state.clear_data()
                    state.mcp_servers = []
                    state.credits_remaining = 50
                    state.user_uuid = ""
                    _update_mcp_list()
                    page.snack_bar = ft.SnackBar(
                        content=ft.Text("All local data cleared."),
                        duration=2000,
                    )
                    page.snack_bar.open = True
                    page.update()

            return _close

        dialog = ft.AlertDialog(
            title=ft.Text("Clear All Data?"),
            content=ft.Text(
                "This will delete your local UUID, credits, and settings. "
                "While your secure cloud-side backup registration remains active, "
                "you MUST have your 12-word recovery seed phrase saved to restore "
                "your account and credits. Without it, your account and credits "
                "CANNOT be recovered!\n\n"
                "Are you sure you want to proceed?"
            ),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog(False)),
                ft.FilledButton(
                    "Clear Everything",
                    style=ft.ButtonStyle(bgcolor=theme.ERROR),
                    on_click=close_dialog(True),
                ),
            ],
        )
        show_dialog(dialog)

    async def _share_invite(e):
        """Share the user's invite code (first 8 chars of UUID)."""
        invite_code = state.user_uuid[:8] if state.user_uuid else ""
        if invite_code:
            await page.clipboard.set(invite_code)
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Invite code copied: {invite_code}"),
                duration=3000,
            )
            page.snack_bar.open = True
            page.update()

    async def _enter_referral_code(e):
        """Prompt for a friend's invite code and apply the referral bonus."""
        code_field = ft.Ref[ft.TextField]()

        async def _apply(ev):
            code = code_field.current.value.strip() if code_field.current else ""
            if not code or len(code) < 6:
                page.snack_bar = ft.SnackBar(
                    ft.Text("Code must be at least 6 characters."),
                    duration=3000,
                )
                page.snack_bar.open = True
                page.update()
                return
            # Register referral via gateway
            try:
                from core.constants import API_BASE_URL
                from services.api_client import request_with_retry

                resp = await request_with_retry(
                    "POST",
                    f"{API_BASE_URL}/referrals",
                    json={
                        "referrer_uuid": code,
                        "referred_uuid": state.user_uuid,
                    },
                    timeout=10.0,
                )
                if resp.status_code == 201:
                    new_cap = await credit_service.add_referral_bonus()
                    state.credits_remaining = await credit_service.get_balance()
                    page.snack_bar = ft.SnackBar(
                        ft.Text(f"Bonus applied! Daily cap now {new_cap}"),
                        duration=3000,
                    )
                elif resp.status_code == 409:
                    page.snack_bar = ft.SnackBar(
                        ft.Text("Already used this code."),
                        duration=3000,
                    )
                else:
                    page.snack_bar = ft.SnackBar(
                        ft.Text("Invalid code. Try again."),
                        duration=3000,
                    )
            except Exception:
                page.snack_bar = ft.SnackBar(
                    ft.Text("Network error. Try again."),
                    duration=3000,
                )

            await close_dialog_helper(dialog)
            page.snack_bar.open = True
            page.update()

        async def _cancel(ev):
            await close_dialog_helper(dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("Enter Invite Code"),
            content=ft.TextField(
                ref=code_field,
                hint_text="Paste a friend's invite code",
                border_radius=tokens.RADIUS_MD,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_cancel),
                ft.FilledButton(
                    "Apply",
                    on_click=lambda ev: page.run_task(_apply, ev),
                ),
            ],
        )
        show_dialog(dialog)

    # ── MCP Server Actions ──────────────────────────────────────────
    mcp_column_ref = ft.Ref[ft.Column]()

    def _build_mcp_list_controls() -> list[ft.Control]:
        controls = []
        if not state.mcp_servers:
            controls.append(
                ft.Container(
                    content=ft.Text(
                        "No MCP servers configured.",
                        size=tokens.FONT_SM,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        italic=True,
                    ),
                    padding=ft.Padding(
                        tokens.SPACE_LG,
                        tokens.SPACE_SM,
                        tokens.SPACE_LG,
                        tokens.SPACE_SM,
                    ),
                )
            )
        else:
            for idx, srv in enumerate(state.mcp_servers):
                status = srv.get("status", "Disconnected")
                tools_list = srv.get("tools", [])
                tools_cnt = len(tools_list)
                is_enabled = srv.get("enabled", True)

                # Determine status color & icon
                if status == "Connected":
                    status_icon = ft.Icons.LINK_ROUNDED
                    status_color = ft.Colors.PRIMARY
                elif status == "Error":
                    status_icon = ft.Icons.LINK_OFF_ROUNDED
                    status_color = theme.ERROR
                else:
                    status_icon = ft.Icons.LINK_ROUNDED
                    status_color = ft.Colors.ON_SURFACE_VARIANT

                def make_refresh_handler(i=idx):
                    async def _ref(ev):
                        state.mcp_servers[i]["status"] = "Connecting..."
                        _update_mcp_list()

                        srv_info = state.mcp_servers[i]
                        success, tools = await mcp_manager.connect_server(
                            srv_info["name"],
                            srv_info["url"],
                            headers=srv_info.get("headers"),
                        )

                        target_server = state.mcp_servers[i]
                        target_server["status"] = "Connected" if success else "Error"

                        # Preserve tool enabled statuses on refresh
                        old_enabled = {
                            t["name"]: t.get("enabled", True)
                            for t in target_server.get("tools", [])
                        }
                        for tool in tools:
                            tool["enabled"] = old_enabled.get(tool["name"], True)

                        target_server["tools"] = tools
                        # Save updated status/tools to storage
                        if storage:
                            await storage.set(
                                STORAGE_MCP_SERVERS, json.dumps(state.mcp_servers)
                            )
                        _update_mcp_list()

                    return _ref

                def make_delete_handler(i=idx):
                    async def _del(ev):
                        state.mcp_servers.pop(i)
                        if storage:
                            await storage.set(
                                STORAGE_MCP_SERVERS, json.dumps(state.mcp_servers)
                            )
                        _update_mcp_list()

                    return _del

                def make_toggle_server_handler(i=idx):
                    async def _toggle(ev):
                        state.mcp_servers[i]["enabled"] = ev.control.value
                        if storage:
                            await storage.set(
                                STORAGE_MCP_SERVERS, json.dumps(state.mcp_servers)
                            )
                        _update_mcp_list()

                    return _toggle

                def make_toggle_tool_handler(server_idx=idx, tool_idx=None):
                    async def _toggle(ev):
                        state.mcp_servers[server_idx]["tools"][tool_idx]["enabled"] = (
                            ev.control.value
                        )
                        if storage:
                            await storage.set(
                                STORAGE_MCP_SERVERS, json.dumps(state.mcp_servers)
                            )
                        _update_mcp_list()

                    return _toggle

                # Build subcontrols for inside the ExpansionTile
                tool_controls = []
                tool_controls.append(
                    ft.ListTile(
                        leading=ft.Icon(
                            ft.Icons.POWER_SETTINGS_NEW_ROUNDED,
                            color=ft.Colors.PRIMARY
                            if is_enabled
                            else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        title=ft.Text(
                            "Enable Server",
                            size=tokens.FONT_SM,
                            weight=ft.FontWeight.W_500,
                        ),
                        subtitle=ft.Text(
                            "Include server tools in AI context", size=tokens.FONT_XS
                        ),
                        trailing=ft.Switch(
                            value=is_enabled,
                            on_change=make_toggle_server_handler(idx),
                            active_color=ft.Colors.PRIMARY,
                        ),
                        dense=True,
                    )
                )
                tool_controls.append(
                    ft.Divider(height=1, thickness=1, color=ft.Colors.SURFACE_VARIANT)
                )

                tool_controls.append(
                    ft.Container(
                        content=ft.Text(
                            "AVAILABLE TOOLS",
                            size=tokens.FONT_XXS,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.PRIMARY,
                        ),
                        padding=ft.Padding(
                            left=tokens.SPACE_LG,
                            top=tokens.SPACE_SM,
                            bottom=tokens.SPACE_XXS,
                            right=0,
                        ),
                    )
                )

                if not tools_list:
                    tool_controls.append(
                        ft.ListTile(
                            title=ft.Text(
                                "No tools loaded.", size=tokens.FONT_SM, italic=True
                            ),
                            dense=True,
                        )
                    )
                else:
                    for t_idx, tool in enumerate(tools_list):
                        tool_enabled = tool.get("enabled", True)
                        tool_controls.append(
                            ft.ListTile(
                                leading=ft.Icon(
                                    ft.Icons.BUILD_OUTLINED,
                                    size=tokens.ICON_SM,
                                    color=ft.Colors.PRIMARY
                                    if (is_enabled and tool_enabled)
                                    else ft.Colors.ON_SURFACE_VARIANT,
                                ),
                                title=ft.Text(
                                    tool["name"],
                                    size=tokens.FONT_SM,
                                    weight=ft.FontWeight.W_500,
                                ),
                                subtitle=ft.Text(
                                    tool.get("description", "No description available"),
                                    size=tokens.FONT_XS,
                                ),
                                trailing=ft.Switch(
                                    value=tool_enabled,
                                    on_change=make_toggle_tool_handler(idx, t_idx),
                                    active_color=ft.Colors.PRIMARY,
                                    disabled=not is_enabled,
                                ),
                                dense=True,
                            )
                        )

                # Custom Card layout for the ExpansionTile
                controls.append(
                    ft.Container(
                        content=ft.ExpansionTile(
                            title=ft.Row(
                                [
                                    ft.Text(
                                        srv["name"],
                                        size=tokens.FONT_MD,
                                        weight=ft.FontWeight.W_500,
                                        expand=True,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.REFRESH_ROUNDED,
                                        icon_color=ft.Colors.PRIMARY,
                                        icon_size=18,
                                        tooltip="Refresh connection",
                                        on_click=make_refresh_handler(),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_ROUNDED,
                                        icon_color=theme.ERROR,
                                        icon_size=18,
                                        tooltip="Delete server",
                                        on_click=make_delete_handler(),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            subtitle=ft.Text(
                                f"{srv['url']}\n{status} \u2022 {tools_cnt} tools",
                                size=tokens.FONT_XS,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            leading=ft.Icon(status_icon, color=status_color),
                            controls=tool_controls,
                        ),
                        bgcolor=theme.GLASS_BG,
                        border=ft.Border.all(1, theme.GLASS_BORDER_COLOR),
                        border_radius=tokens.RADIUS_MD,
                        margin=ft.Margin(
                            left=tokens.SPACE_LG,
                            right=tokens.SPACE_LG,
                            top=tokens.SPACE_XS,
                            bottom=tokens.SPACE_XS,
                        ),
                    )
                )
        return controls

    def _update_mcp_list():
        if mcp_column_ref.current:
            mcp_column_ref.current.controls = _build_mcp_list_controls()
            mcp_column_ref.current.update()

    async def on_add_mcp_server(e):
        name_field = ft.Ref[ft.TextField]()
        url_field = ft.Ref[ft.TextField]()
        headers_field = ft.Ref[ft.TextField]()
        status_text = ft.Ref[ft.Text]()
        progress_bar = ft.Ref[ft.ProgressBar]()

        async def _connect_and_save(ev):
            name = name_field.current.value.strip() if name_field.current else ""
            url = url_field.current.value.strip() if url_field.current else ""
            headers_val = (
                headers_field.current.value.strip() if headers_field.current else ""
            )

            if not name or not url:
                if status_text.current:
                    status_text.current.value = "Name and URL are required."
                    status_text.current.color = theme.ERROR
                    status_text.current.update()
                return

            headers = {}
            if headers_val:
                for line in headers_val.split("\n"):
                    if ":" in line:
                        k, v = line.split(":", 1)
                        headers[k.strip()] = v.strip()

            if progress_bar.current:
                progress_bar.current.visible = True
                progress_bar.current.update()

            if status_text.current:
                status_text.current.value = "Connecting to SSE endpoint..."
                status_text.current.color = ft.Colors.PRIMARY
                status_text.current.update()

            success, tools = await mcp_manager.connect_server(
                name, url, headers=headers
            )

            if progress_bar.current:
                progress_bar.current.visible = False
                progress_bar.current.update()

            if success:
                new_server = {
                    "name": name,
                    "url": url,
                    "headers": headers,
                    "status": "Connected",
                    "enabled": True,
                    "tools": tools,
                }
                state.mcp_servers.append(new_server)
                if storage:
                    await storage.set(
                        STORAGE_MCP_SERVERS, json.dumps(state.mcp_servers)
                    )

                _update_mcp_list()
                await close_dialog_helper(dialog)
            else:
                if status_text.current:
                    status_text.current.value = (
                        "Connection failed. Check SSE endpoint URL."
                    )
                    status_text.current.color = theme.ERROR
                    status_text.current.update()

        async def _cancel(ev):
            await close_dialog_helper(dialog)

        dialog = ft.AlertDialog(
            title=ft.Text("Add MCP Server"),
            content=ft.Column(
                [
                    ft.TextField(
                        ref=name_field,
                        label="Server Name",
                        hint_text="e.g. Google Sheets",
                        border_radius=tokens.RADIUS_MD,
                    ),
                    ft.TextField(
                        ref=url_field,
                        label="SSE Endpoint URL",
                        hint_text="e.g. http://localhost:3001/sse",
                        border_radius=tokens.RADIUS_MD,
                    ),
                    ft.TextField(
                        ref=headers_field,
                        label="Headers (Optional)",
                        hint_text="e.g. Authorization: Token YOUR_KEY",
                        border_radius=tokens.RADIUS_MD,
                        multiline=True,
                        min_lines=1,
                        max_lines=2,
                    ),
                    ft.Text(
                        ref=status_text,
                        size=tokens.FONT_XS,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.ProgressBar(ref=progress_bar, visible=False),
                ],
                spacing=tokens.SPACE_MD,
                height=260,
                width=300,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_cancel),
                ft.FilledButton(
                    "Connect & Add",
                    on_click=lambda ev: page.run_task(_connect_and_save, ev),
                ),
            ],
        )
        show_dialog(dialog)

    phrase_subtitle = ft.Text(
        "Copy your recovery phrase",
        size=tokens.FONT_XS,
        color=ft.Colors.ON_SURFACE_VARIANT,
    )

    async def check_sync_status():
        is_synced = await uuid_service.is_synced()
        if not is_synced:
            # Try syncing once more when they visit settings
            synced = await uuid_service.sync_pending_uuid()
            if synced:
                phrase_subtitle.value = "Copy your recovery phrase (Synced)"
                phrase_subtitle.color = theme.SUCCESS
            else:
                phrase_subtitle.value = "⚠️ Backup phrase NOT synced to cloud!"
                phrase_subtitle.color = theme.ERROR
        else:
            phrase_subtitle.value = "Copy your recovery phrase (Synced)"
            phrase_subtitle.color = theme.SUCCESS
        try:
            phrase_subtitle.update()
        except Exception:
            pass

    page.run_task(check_sync_status)

    masked_uuid = uuid_service.get_masked_uuid(state.user_uuid)

    # Theme dropdown value
    current_theme = "light"
    if page.theme_mode == ft.ThemeMode.DARK:
        current_theme = "dark"
    elif page.theme_mode == ft.ThemeMode.SYSTEM:
        current_theme = "system"

    content = ft.Column(
        controls=[
            # ── Account Section ─────────────────────────────────
            section_header("Account"),
            setting_tile(
                icon=ft.Icons.FINGERPRINT_ROUNDED,
                title="Your ID",
                subtitle=masked_uuid,
                trailing=ft.IconButton(
                    icon=ft.Icons.COPY_ROUNDED,
                    icon_size=tokens.ICON_MD,
                    tooltip="Copy full UUID",
                    on_click=lambda e: page.run_task(on_copy_uuid, e),
                ),
            ),
            setting_tile(
                icon=ft.Icons.KEY_ROUNDED,
                title="Backup Phrase",
                subtitle=phrase_subtitle,
                trailing=ft.IconButton(
                    icon=ft.Icons.COPY_ALL_ROUNDED,
                    icon_size=tokens.ICON_MD,
                    tooltip="Copy phrase",
                    on_click=lambda e: page.run_task(on_copy_phrase, e),
                ),
            ),
            # ── Credits Section ─────────────────────────────────
            section_header("Credits"),
            setting_tile(
                icon=ft.Icons.BOLT_ROUNDED,
                title="Daily Credits",
                subtitle=f"{state.credits_remaining} remaining today",
            ),
            setting_tile(
                icon=ft.Icons.PEOPLE_ROUNDED,
                title="Invite Friends",
                subtitle="Get +10 daily credits per referral",
                trailing=ft.IconButton(
                    icon=ft.Icons.SHARE_ROUNDED,
                    icon_size=tokens.ICON_MD,
                    tooltip="Share invite code",
                    on_click=lambda e: page.run_task(_share_invite, e),
                ),
            ),
            setting_tile(
                icon=ft.Icons.CARD_GIFTCARD_ROUNDED,
                title="Enter Invite Code",
                subtitle="Paste a friend's code to unlock bonus credits",
                trailing=ft.IconButton(
                    icon=ft.Icons.INPUT_ROUNDED,
                    icon_size=tokens.ICON_MD,
                    tooltip="Enter code",
                    on_click=lambda e: page.run_task(_enter_referral_code, e),
                ),
            ),
            # ── Appearance Section ──────────────────────────────
            section_header("Appearance"),
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.PALETTE_ROUNDED,
                            size=tokens.ICON_LG,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "Theme",
                            size=tokens.FONT_MD,
                            weight=ft.FontWeight.W_500,
                            expand=True,
                        ),
                        ft.Dropdown(
                            value=current_theme,
                            width=130,
                            options=[
                                ft.DropdownOption(key="light", text="Light"),
                                ft.DropdownOption(key="dark", text="Dark"),
                                ft.DropdownOption(key="system", text="System"),
                            ],
                            on_select=lambda e: page.run_task(on_theme_changed, e),
                            border_radius=tokens.RADIUS_MD,
                            text_size=tokens.FONT_SM,
                        ),
                    ],
                    spacing=tokens.SPACE_LG,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(
                    left=tokens.SPACE_LG,
                    right=tokens.SPACE_LG,
                    top=14,
                    bottom=14,
                ),
            ),
            # ── Model Context Protocol (MCP) Section ───────────────────────────
            section_header("Model Context Protocol (MCP)"),
            setting_tile(
                icon=ft.Icons.ADD_LINK_ROUNDED,
                title="Add MCP Server",
                subtitle="Connect remote tool servers (Google Slides, Sheets, SQL)",
                on_click=lambda e: page.run_task(on_add_mcp_server, e),
            ),
            ft.Column(
                ref=mcp_column_ref,
                controls=_build_mcp_list_controls(),
                spacing=tokens.SPACE_XXS,
            ),
            # ── Data Section ────────────────────────────────────
            section_header("Data"),
            setting_tile(
                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                title="Clear All Local Data",
                subtitle="Remove UUID, credits, and cached data",
                on_click=lambda e: page.run_task(on_clear_data, e),
            ),
            # ── Pro Tier Tease ──────────────────────────────────
            section_header("Premium"),
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                            size=tokens.ICON_LG,
                            color=ft.Colors.with_opacity(0.4, theme.PRIMARY),
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "Spaninsight Pro",
                                    size=tokens.FONT_MD,
                                    weight=ft.FontWeight.W_500,
                                    color=ft.Colors.with_opacity(
                                        0.5, ft.Colors.ON_SURFACE
                                    ),
                                ),
                                ft.Text(
                                    "Zero ads \u2022 Priority AI \u2022 Unlimited credits",
                                    size=tokens.FONT_XS,
                                    color=ft.Colors.with_opacity(
                                        0.35, ft.Colors.ON_SURFACE
                                    ),
                                ),
                            ],
                            spacing=tokens.SPACE_XXS,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Text(
                                "SOON",
                                size=tokens.FONT_XXS,
                                weight=ft.FontWeight.W_700,
                                color=theme.PRIMARY_LIGHT,
                            ),
                            padding=ft.Padding(
                                left=tokens.SPACE_SM,
                                right=tokens.SPACE_SM,
                                top=tokens.SPACE_XXS,
                                bottom=tokens.SPACE_XXS,
                            ),
                            border_radius=tokens.RADIUS_SM,
                            bgcolor=ft.Colors.with_opacity(0.1, theme.PRIMARY),
                        ),
                    ],
                    spacing=tokens.SPACE_LG,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(
                    left=tokens.SPACE_LG,
                    right=tokens.SPACE_LG,
                    top=14,
                    bottom=14,
                ),
                border_radius=tokens.RADIUS_MD,
                opacity=0.6,
            ),
            # ── About Section ──────────────────────────────────
            section_header("About"),
            setting_tile(
                icon=ft.Icons.INFO_OUTLINE_ROUNDED,
                title="Version",
                subtitle="Spaninsight v1.0.0",
            ),
            setting_tile(
                icon=ft.Icons.PRIVACY_TIP_OUTLINED,
                title="Privacy Policy",
                subtitle="Your data never leaves your device",
            ),
            ft.Container(height=tokens.SPACE_XL),
            ft.Container(
                content=build_brand_header(show_tagline=True, spacing_below=False),
                opacity=0.6,
            ),
            ft.Container(height=tokens.SPACE_XXXL),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=tokens.SPACE_XXS,
    )

    appbar = ft.AppBar(
        title=ft.Text("Settings", weight=ft.FontWeight.W_600, size=tokens.FONT_XL),
        center_title=False,
        bgcolor=ft.Colors.TRANSPARENT,
    )

    return ft.View(route="/settings", appbar=appbar, controls=[content], padding=0)
