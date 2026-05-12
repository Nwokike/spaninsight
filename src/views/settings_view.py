"""Settings view — UUID backup, credits, theme, pro tease."""

from __future__ import annotations

import logging

import flet as ft

from core import theme, tokens
from core.state import state
from core.constants import STORAGE_THEME
from core.styles import section_header, setting_tile
from flet_secure_storage import SecureStorage

logger = logging.getLogger(__name__)


def build_settings_view(
    page: ft.Page,
    uuid_service,
    credit_service,
) -> ft.View:
    """Build the Settings tab view."""

    async def on_copy_uuid(e):
        user_uuid = await uuid_service.get_uuid()
        if user_uuid:
            page.clipboard = user_uuid
            page.snack_bar = ft.SnackBar(
                content=ft.Text("UUID copied to clipboard"),
                duration=2000,
            )
            page.snack_bar.open = True
            page.update()

    async def on_copy_phrase(e):
        phrase = await uuid_service.get_backup_phrase()
        if phrase:
            page.clipboard = phrase
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
        storage = SecureStorage()
        await storage.set(STORAGE_THEME, mode)
        
        page.update()

    async def on_clear_data(e):
        def close_dialog(confirmed):
            async def _close(ev):
                dialog.open = False
                page.update()
                if confirmed:
                    state.clear_data()
                    state.credits_remaining = 50
                    state.user_uuid = ""
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
                "This will delete your UUID, credits, and all local data. "
                "This action cannot be undone."
            ),
            actions=[
                ft.TextButton("Cancel", on_click=await close_dialog(False)),
                ft.FilledButton(
                    "Clear Everything",
                    style=ft.ButtonStyle(bgcolor=theme.ERROR),
                    on_click=await close_dialog(True),
                ),
            ],
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    async def _share_invite(e):
        """Share the user's invite code (first 8 chars of UUID)."""
        invite_code = state.user_uuid[:8] if state.user_uuid else ""
        if invite_code:
            page.clipboard = invite_code
            page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Invite code copied: {invite_code}"),
                duration=3000,
            )
            page.snack_bar.open = True
            page.update()

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
                subtitle="Copy your recovery phrase",
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
                                    color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                                ),
                                ft.Text(
                                    "Zero ads \u2022 Priority AI \u2022 Unlimited credits",
                                    size=tokens.FONT_XS,
                                    color=ft.Colors.with_opacity(0.35, ft.Colors.ON_SURFACE),
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
