# -*- coding: utf-8 -*-
"""Centralized design tokens for the ScarTools design system.

Single source of truth for all dimensions, typography, colors, borders, and animations.
"""

from __future__ import absolute_import, division, print_function

# -----------------------------------------------------------------------------
# 1. Typography & Font Families
# -----------------------------------------------------------------------------
FONT_FAMILY_BASE = '"Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif'
FONT_FAMILY_MONO = 'Consolas, "Roboto Mono", "Courier New", monospace'

FONT_SIZE_TITLE = 16
FONT_SIZE_HEADER = 14
FONT_SIZE_SECTION = 12
FONT_SIZE_BODY = 12
FONT_SIZE_SUBTITLE = 11
FONT_SIZE_LABEL = 11
FONT_SIZE_BADGE = 10
FONT_SIZE_CODE = 11

FONT_WEIGHT_NORMAL = 400
FONT_WEIGHT_MEDIUM = 500
FONT_WEIGHT_SEMIBOLD = 600
FONT_WEIGHT_BOLD = 700

# -----------------------------------------------------------------------------
# 2. Color Palette (Dark Theme)
# -----------------------------------------------------------------------------
# Surfaces
COLOR_BG_ROOT = "#242424"
COLOR_BG_PANEL = "#292929"
COLOR_BG_DARK = "#202020"
COLOR_BG_INPUT = "#181818"
COLOR_BG_INPUT_FOCUS = "#1E1E1E"
COLOR_BG_INPUT_READONLY = "#141414"

# Borders
COLOR_BORDER_DEFAULT = "#3A3A3A"
COLOR_BORDER_INPUT = "#484848"
COLOR_BORDER_FOCUS = "#83A6DA"
COLOR_BORDER_SUBTLE = "#303030"

# Text & Foreground
COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_SECONDARY = "#D8D8D8"
COLOR_TEXT_LABEL = "#D2D2D2"
COLOR_TEXT_MUTED = "#AFAFAF"
COLOR_TEXT_DISABLED = "#666666"

# Primary / Accent Colors
COLOR_PRIMARY_BLUE = "#4F78B8"
COLOR_PRIMARY_BLUE_HOVER = "#5C87C8"
COLOR_PRIMARY_BLUE_BORDER = "#6E94CE"

COLOR_ACTION_BTN = "#3A4759"
COLOR_ACTION_BTN_HOVER = "#48586E"
COLOR_ACTION_BTN_BORDER = "#5A6E8A"
COLOR_ACTION_BTN_PRESSED = "#2D3745"

COLOR_PRESET_BTN = "#30333A"
COLOR_PRESET_BTN_HOVER = "#404552"
COLOR_PRESET_BTN_BORDER = "#484D58"
COLOR_PRESET_BTN_TEXT = "#DDE2EC"

# Department Accents
COLOR_ACCENT_MODELING = "#5F7FA8"
COLOR_ACCENT_RIGGING = "#766A8E"
COLOR_ACCENT_TEXTURING = "#A67C45"
COLOR_ACCENT_PIPELINE = "#4E937B"
COLOR_ACCENT_CLEANUP = "#A67C45"
COLOR_ACCENT_MIRROR = "#766A8E"
COLOR_ACCENT_COPY = "#5684BD"
COLOR_ACCENT_CLUSTER = "#4E937B"

# Status & Diagnostics
COLOR_STATUS_SUCCESS = "#72D6AA"
COLOR_STATUS_WARNING = "#D6B36A"
COLOR_STATUS_ERROR = "#E06C6C"
COLOR_STATUS_INFO = "#79A9E6"
COLOR_STATUS_IDLE = "#C7C7C7"

# Console & Filter Chips
COLOR_CONSOLE_BG = "#16171A"
COLOR_CONSOLE_LINE = "#1C1E24"
COLOR_CHIP_ALL = "#383E48"
COLOR_CHIP_ALL_ACTIVE = "#4F78B8"
COLOR_CHIP_ERROR_ACTIVE = "#9E3C3C"
COLOR_CHIP_WARNING_ACTIVE = "#A88338"
COLOR_CHIP_SUCCESS_ACTIVE = "#368A62"
COLOR_CHIP_INFO_ACTIVE = "#3B6DA8"

# 3D Axes & Interactive Tags
COLOR_AXIS_X = "#A63434"
COLOR_AXIS_Y = "#3B7D44"
COLOR_AXIS_Z = "#3B5F9E"
COLOR_TAG_BG = "#2D323B"
COLOR_TAG_BORDER = "#4C566A"

# -----------------------------------------------------------------------------
# 3. Layout & Dimension Metrics
# -----------------------------------------------------------------------------
# Standard Spacing Scale
SPACE_XS = 4       # Tight icon/text gap, badge internal padding
SPACE_S = 6        # Compact internal spacing, grid vertical spacing
SPACE_M = 8        # Standard control spacing, horizontal item spacing
SPACE_L = 12       # Component padding, section panel margins
SPACE_XL = 16      # Section-to-section gap
SPACE_XXL = 20     # Major panel / workflow group spacing

# Root Window Dimensions
WINDOW_MARGIN = 10
WINDOW_SPACING = 10

# Section & Group Dimensions
GROUP_MARGIN_X = 12
GROUP_MARGIN_TOP = 10
GROUP_MARGIN_BOTTOM = 10
GROUP_SPACING = 8
CARD_SPACING = 10
NAV_CONTENT_GAP = 10

# Standardized Control Heights
CONTROL_HEIGHT = 28
FIELD_HEIGHT = 28
BUTTON_HEIGHT = 30
SECONDARY_BUTTON_HEIGHT = 30
COMPACT_BUTTON_HEIGHT = 26
PRIMARY_BUTTON_HEIGHT = 38
HEADER_HEIGHT = 54
TAB_HEIGHT = 28
TABLE_ROW_HEIGHT = 26
TABLE_HEADER_HEIGHT = 28

# Width Constants
SECONDARY_BUTTON_MIN_WIDTH = 70
PRIMARY_BUTTON_WIDTH = 220
FORM_ACTION_WIDTH = 150
LOG_BUTTON_WIDTH = 84
CLOSE_BUTTON_WIDTH = 70
TABLE_MIN_HEIGHT = 240
TABLE_STATUS_WIDTH = 105
FORM_LABEL_WIDTH = 65
INLINE_SPACING = 10
STATUS_DOT_WIDTH = 20
ACTION_FOOTER_MIN_HEIGHT = 56

__all__ = [name for name in globals() if name.isupper()]

