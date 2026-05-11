"""Design system — spacing, radius, typography and sizing tokens.

Every magic number used anywhere in Spaninsight lives here.
Mirrors the token system used in Fletbot/KTV Player.
"""

from __future__ import annotations

# ── Border Radii ────────────────────────────────────────────────────
RADIUS_XS = 4
RADIUS_SM = 8
RADIUS_MD = 12
RADIUS_LG = 16
RADIUS_XL = 20
RADIUS_XXL = 24
RADIUS_PILL = 100

# ── Spacing (padding / margin / gaps) ───────────────────────────────
SPACE_XXS = 2
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 20
SPACE_XXL = 24
SPACE_XXXL = 32
SPACE_XXXXL = 40

# ── Font Sizes ──────────────────────────────────────────────────────
FONT_XXS = 10
FONT_XS = 12
FONT_SM = 13
FONT_MD = 15
FONT_LG = 18
FONT_XL = 20
FONT_XXL = 24
FONT_TITLE = 28
FONT_HERO = 36

# ── Icon Sizes ──────────────────────────────────────────────────────
ICON_SM = 18
ICON_MD = 20
ICON_LG = 24
ICON_XL = 32
ICON_XXL = 48
ICON_HERO = 64

# ── Blur Sigma ──────────────────────────────────────────────────────
BLUR_SM = 10
BLUR_MD = 20
BLUR_LG = 30

# ── Shadow ──────────────────────────────────────────────────────────
SHADOW_BLUR = 12
SHADOW_BLUR_LG = 24
SHADOW_OFFSET_Y = 4
SHADOW_OFFSET_Y_LG = 8

# ── Layout ──────────────────────────────────────────────────────────
NAV_BAR_HEIGHT = 70
CARD_MAX_WIDTH = 600
INPUT_HEIGHT = 48

# ── Animation ───────────────────────────────────────────────────────
ANIM_FAST_MS = 150
ANIM_DEFAULT_MS = 300
ANIM_SLOW_MS = 500
