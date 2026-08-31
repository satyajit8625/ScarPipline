# -*- coding: utf-8 -*-
"""
Centralized Modern DCC Components inspired by Refactoring UI.

Provides:
- StatusBadge / create_badge: Contrast-flipped pill badges ([✓ Verified], [🔒 Standard])
- AlertCallout / create_alert_callout: Informational/Warning/Success callout cards
- CollapsibleCard / create_collapsible_card: Reusable accordion panel for advanced options
- EmptyStateWidget / create_empty_state: Centered empty placeholder for tables and lists
- SearchInput / create_search_input: Recessed filter search input with clear icon
- KeyValuePairWidget / create_key_value_row: High-contrast data presentation row
"""

from __future__ import absolute_import, division, print_function

from .qt import QtCore, QtGui, QtWidgets
from .tokens import (
    FONT_FAMILY_BASE,
    FONT_FAMILY_MONO,
    SPACE_XS,
    SPACE_SM,
    SPACE_MD,
    SPACE_LG,
    LETTER_SPACING_BADGE,
    LETTER_SPACING_HEADER,
    COLOR_BADGE_SUCCESS_BG,
    COLOR_BADGE_SUCCESS_BORDER,
    COLOR_BADGE_SUCCESS_TEXT,
    COLOR_BADGE_WARNING_BG,
    COLOR_BADGE_WARNING_BORDER,
    COLOR_BADGE_WARNING_TEXT,
    COLOR_BADGE_ERROR_BG,
    COLOR_BADGE_ERROR_BORDER,
    COLOR_BADGE_ERROR_TEXT,
    COLOR_BADGE_INFO_BG,
    COLOR_BADGE_INFO_BORDER,
    COLOR_BADGE_INFO_TEXT,
    COLOR_BADGE_NEUTRAL_BG,
    COLOR_BADGE_NEUTRAL_BORDER,
    COLOR_BADGE_NEUTRAL_TEXT,
    COLOR_BG_PANEL,
    COLOR_BG_WELL,
    COLOR_BORDER_DEFAULT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_PRIMARY_BLUE,
)


# ==============================================================================
# 1. Status Badge Component (Contrast-Flipped Pill)
# ==============================================================================

class StatusBadge(QtWidgets.QLabel):
    """
    Modern pill badge displaying concise semantic state with contrast-flipped tint.
    Example: [✓ Verified], [🔒 Standard], [⚠️ Attention], [❌ Issue]
    """

    VARIANT_STYLES = {
        "success": (COLOR_BADGE_SUCCESS_BG, COLOR_BADGE_SUCCESS_BORDER, COLOR_BADGE_SUCCESS_TEXT),
        "warning": (COLOR_BADGE_WARNING_BG, COLOR_BADGE_WARNING_BORDER, COLOR_BADGE_WARNING_TEXT),
        "error": (COLOR_BADGE_ERROR_BG, COLOR_BADGE_ERROR_BORDER, COLOR_BADGE_ERROR_TEXT),
        "info": (COLOR_BADGE_INFO_BG, COLOR_BADGE_INFO_BORDER, COLOR_BADGE_INFO_TEXT),
        "locked": (COLOR_BADGE_INFO_BG, COLOR_BADGE_INFO_BORDER, "#79A9E6"),
        "neutral": (COLOR_BADGE_NEUTRAL_BG, COLOR_BADGE_NEUTRAL_BORDER, COLOR_BADGE_NEUTRAL_TEXT),
        "pipeline": ("#1B2B22", "#2E523E", "#72D6AA"),
        "modeling": ("#1E2633", "#34455E", "#7DA4D9"),
        "rig": ("#262033", "#45365E", "#A894CF"),
        "texturing": ("#2E2416", "#594324", "#D9A85B"),
    }

    def __init__(self, text="", variant="neutral", parent=None):
        super(StatusBadge, self).__init__(text, parent)
        self._variant = str(variant).lower()
        self.setObjectName("StatusBadge")
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setFixedHeight(22)
        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self._apply_badge_style()

    def set_variant(self, variant):
        self._variant = str(variant).lower()
        self._apply_badge_style()

    def _apply_badge_style(self):
        bg, border, text_color = self.VARIANT_STYLES.get(self._variant, self.VARIANT_STYLES["neutral"])
        self.setStyleSheet("""
            QLabel#StatusBadge {
                background: %s;
                border: 1px solid %s;
                color: %s;
                font-family: %s;
                font-size: 10px;
                font-weight: 600;
                padding: 2px 8px;
                border-radius: 4px;
                letter-spacing: %s;
            }
        """ % (bg, border, text_color, FONT_FAMILY_BASE, LETTER_SPACING_BADGE))


def create_badge(text, variant="neutral", parent=None):
    """Factory helper to construct a standardized StatusBadge."""
    return StatusBadge(text=text, variant=variant, parent=parent)


# ==============================================================================
# 2. Alert Callout Banner Component
# ==============================================================================

class AlertCallout(QtWidgets.QFrame):
    """
    Informational/Warning callout box with a colored left accent border and tinted background.
    """

    ACCENTS = {
        "info": ("#4F78B8", "#1A222D"),
        "success": ("#4E937B", "#1B2B22"),
        "warning": ("#D6B36A", "#2B2418"),
        "error": ("#E06C6C", "#2B1A1A"),
        "neutral": ("#505050", "#222428"),
    }

    def __init__(self, title="", message="", variant="info", parent=None):
        super(AlertCallout, self).__init__(parent)
        self.setObjectName("AlertCallout")
        self._variant = str(variant).lower()
        self._title = title
        self._message = message
        self._build_ui()

    def _build_ui(self):
        accent_color, bg_color = self.ACCENTS.get(self._variant, self.ACCENTS["info"])
        self.setStyleSheet("""
            QFrame#AlertCallout {
                background: %s;
                border: 1px solid #333842;
                border-left: 4px solid %s;
                border-radius: 6px;
            }
        """ % (bg_color, accent_color))

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        if self._title:
            title_lbl = QtWidgets.QLabel(self._title, self)
            title_lbl.setStyleSheet("color: #FFFFFF; font-weight: 600; font-size: 11px;")
            layout.addWidget(title_lbl)

        if self._message:
            msg_lbl = QtWidgets.QLabel(self._message, self)
            msg_lbl.setWordWrap(True)
            msg_lbl.setStyleSheet("color: #B0B8C4; font-size: 11px;")
            layout.addWidget(msg_lbl)


def create_alert_callout(title="", message="", variant="info", parent=None):
    """Factory helper to construct an AlertCallout banner."""
    return AlertCallout(title=title, message=message, variant=variant, parent=parent)


# ==============================================================================
# 3. Collapsible Card / Accordion Section Component
# ==============================================================================

class CollapsibleCard(QtWidgets.QFrame):
    """
    Standardized accordion container with chevron toggle, count badge, and smooth expanding container.
    """

    toggled = QtCore.Signal(bool)

    def __init__(self, title="Advanced Options", count=None, collapsed=True, parent=None):
        super(CollapsibleCard, self).__init__(parent)
        self.setObjectName("CollapsibleCard")
        self._title_text = title
        self._count = count
        self._is_collapsed = bool(collapsed)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QFrame#CollapsibleCard {
                background: #202227;
                border: 1px solid #333740;
                border-radius: 6px;
            }
        """)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(6)

        # Header Bar
        header_bar = QtWidgets.QHBoxLayout()
        header_bar.setSpacing(8)

        count_str = "  [%d options]" % self._count if self._count is not None else ""
        chevron = "▸" if self._is_collapsed else "▾"
        self.toggle_btn = QtWidgets.QPushButton("%s  %s%s" % (chevron, self._title_text, count_str), self)
        self.toggle_btn.setObjectName("AccordionHeader")
        self.toggle_btn.setFlat(True)
        self.toggle_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.toggle_btn.setStyleSheet("""
            QPushButton#AccordionHeader {
                text-align: left;
                color: #8A94A6;
                font-weight: 600;
                font-size: 11px;
                padding: 2px 0;
                border: none;
            }
            QPushButton#AccordionHeader:hover {
                color: #FFFFFF;
            }
        """)

        header_bar.addWidget(self.toggle_btn)
        header_bar.addStretch(1)
        root.addLayout(header_bar)

        # Content Container
        self.content_widget = QtWidgets.QWidget(self)
        self.content_widget.setVisible(not self._is_collapsed)
        self.content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 4, 0, 0)
        self.content_layout.setSpacing(6)
        root.addWidget(self.content_widget)

        self.toggle_btn.clicked.connect(self._on_toggle)

    def _on_toggle(self):
        self._is_collapsed = not self._is_collapsed
        self.content_widget.setVisible(not self._is_collapsed)
        chevron = "▸" if self._is_collapsed else "▾"
        count_str = "  [%d options]" % self._count if self._count is not None else ""
        self.toggle_btn.setText("%s  %s%s" % (chevron, self._title_text, count_str))
        self.toggled.emit(not self._is_collapsed)

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)


def create_collapsible_card(title="Advanced Options", count=None, collapsed=True, parent=None):
    """Factory helper to construct a CollapsibleCard accordion."""
    return CollapsibleCard(title=title, count=count, collapsed=collapsed, parent=parent)


# ==============================================================================
# 4. Empty State Widget Component
# ==============================================================================

class EmptyStateWidget(QtWidgets.QFrame):
    """
    Centered empty placeholder container for tables and lists with zero content.
    Displays an icon, clear title, subtitle explanation, and optional action button.
    """

    def __init__(self, title="No Items Found", subtitle="", icon="📂", action_text=None, parent=None):
        super(EmptyStateWidget, self).__init__(parent)
        self.setObjectName("EmptyStateWidget")
        self._title = title
        self._subtitle = subtitle
        self._icon = icon
        self._action_text = action_text
        self.action_button = None
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QFrame#EmptyStateWidget {
                background: #1E2024;
                border: 1px dashed #3A3F4B;
                border-radius: 6px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 24, 20, 24)
        layout.setSpacing(6)
        layout.setAlignment(QtCore.Qt.AlignCenter)

        icon_lbl = QtWidgets.QLabel(self._icon, self)
        icon_lbl.setAlignment(QtCore.Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 26px; background: transparent;")
        layout.addWidget(icon_lbl)

        title_lbl = QtWidgets.QLabel(self._title, self)
        title_lbl.setAlignment(QtCore.Qt.AlignCenter)
        title_lbl.setStyleSheet("color: #FFFFFF; font-weight: 600; font-size: 12px; background: transparent;")
        layout.addWidget(title_lbl)

        if self._subtitle:
            sub_lbl = QtWidgets.QLabel(self._subtitle, self)
            sub_lbl.setAlignment(QtCore.Qt.AlignCenter)
            sub_lbl.setWordWrap(True)
            sub_lbl.setStyleSheet("color: #8A94A6; font-size: 11px; background: transparent;")
            layout.addWidget(sub_lbl)

        if self._action_text:
            self.action_button = QtWidgets.QPushButton(self._action_text, self)
            self.action_button.setFixedHeight(28)
            self.action_button.setStyleSheet("""
                QPushButton {
                    background: #30333A;
                    border: 1px solid #484D58;
                    color: #DDE2EC;
                    border-radius: 4px;
                    padding: 0 14px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background: #3F444E;
                    color: #FFFFFF;
                }
            """)
            layout.addSpacing(6)
            layout.addWidget(self.action_button, 0, QtCore.Qt.AlignCenter)


def create_empty_state(title="No Items Found", subtitle="", icon="📂", action_text=None, parent=None):
    """Factory helper to construct an EmptyStateWidget."""
    return EmptyStateWidget(title=title, subtitle=subtitle, icon=icon, action_text=action_text, parent=parent)


# ==============================================================================
# 5. Search Input Component
# ==============================================================================

class SearchInput(QtWidgets.QLineEdit):
    """
    Recessed table/list filter search bar with search glyph and clear action.
    """

    def __init__(self, placeholder="Filter...", parent=None):
        super(SearchInput, self).__init__(parent)
        self.setObjectName("SearchInput")
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(28)
        self.setClearButtonEnabled(True)
        self.setStyleSheet("""
            QLineEdit#SearchInput {
                background: #18191C;
                border: 1px solid #363C46;
                color: #FFFFFF;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }
            QLineEdit#SearchInput:focus {
                border: 1px solid #83A6DA;
                background: #1E2024;
            }
        """)


def create_search_input(placeholder="Filter...", parent=None):
    """Factory helper to construct a SearchInput."""
    return SearchInput(placeholder=placeholder, parent=parent)


# ==============================================================================
# 6. Key-Value Row Component (De-emphasized Label, High-Contrast Value)
# ==============================================================================

def create_key_value_row(label_text, value_text, is_badge=False, badge_variant="neutral", parent=None):
    """
    Constructs a Refactoring UI compliant Key-Value presentation row.
    Muted label (11px #8A94A6) on left, prominent value or pill badge on right.
    """
    row = QtWidgets.QHBoxLayout()
    row.setContentsMargins(0, 2, 0, 2)
    row.setSpacing(10)

    lbl = QtWidgets.QLabel(str(label_text), parent)
    lbl.setStyleSheet("color: #8A94A6; font-size: 11px; font-weight: 500;")
    row.addWidget(lbl)
    row.addStretch(1)

    if is_badge:
        val_widget = create_badge(text=str(value_text), variant=badge_variant, parent=parent)
        row.addWidget(val_widget)
    else:
        val_lbl = QtWidgets.QLabel(str(value_text), parent)
        val_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        val_lbl.setStyleSheet("color: #FFFFFF; font-size: 11px; font-weight: 600;")
        row.addWidget(val_lbl)

    return row
