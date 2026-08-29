# -*- coding: utf-8 -*-
"""Centralized Global Console & Dockable Log Viewer for all ScarTools packages."""

from __future__ import print_function

import os
import re
import sys
import time

from .qt import QtCore, QtGui, QtWidgets, apply_window_icon, maya_main_window
from .tokens import (
    FONT_FAMILY_BASE,
    FONT_FAMILY_MONO,
    FONT_SIZE_BODY,
    FONT_SIZE_CODE,
    FONT_SIZE_LABEL,
    FONT_SIZE_HEADER,
    COLOR_BG_ROOT,
    COLOR_BG_PANEL,
    COLOR_BG_DARK,
    COLOR_BG_INPUT,
    COLOR_BORDER_DEFAULT,
    COLOR_BORDER_FOCUS,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    COLOR_STATUS_ERROR,
    COLOR_STATUS_INFO,
    COLOR_STATUS_IDLE,
    COLOR_PRIMARY_BLUE,
    COLOR_PRIMARY_BLUE_HOVER,
    COLOR_ACTION_BTN,
    COLOR_ACTION_BTN_HOVER,
    COLOR_CONSOLE_BG,
    COLOR_CHIP_ALL_ACTIVE,
    COLOR_CHIP_ERROR_ACTIVE,
    COLOR_CHIP_WARNING_ACTIVE,
    COLOR_CHIP_SUCCESS_ACTIVE,
    COLOR_CHIP_INFO_ACTIVE,
    FORM_LABEL_WIDTH,
    FIELD_HEIGHT,
    INLINE_SPACING,
    WINDOW_MARGIN,
    WINDOW_SPACING,
)
from .theme import apply as apply_theme
from .window import BaseToolDialog
from ..framework.logging import (
    GlobalLogStore,
    LogEntry,
    LEVEL_INFO,
    LEVEL_SUCCESS,
    LEVEL_WARNING,
    LEVEL_ERROR,
    log_store,
    emit_log,
)


# ===========================================================================
# Filter Chip Button
# ===========================================================================

class FilterChipButton(QtWidgets.QToolButton):
    """Semantic filter chip button with live item count badge."""

    def __init__(self, label, level_key, active_color, parent=None):
        super(FilterChipButton, self).__init__(parent)
        self.level_key = level_key
        self.active_color = active_color
        self._raw_label = label
        self._count = 0
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.setFixedHeight(26)
        self.update_count(0)

    def update_count(self, count):
        self._count = int(count)
        self.setText("{} ({})".format(self._raw_label, self._count))
        self._update_style()

    def setChecked(self, checked):
        super(FilterChipButton, self).setChecked(checked)
        self._update_style()

    def _update_style(self):
        if self.isChecked():
            style = (
                "QToolButton {"
                "  background-color: %s;"
                "  color: #FFFFFF;"
                "  border: 1px solid %s;"
                "  border-radius: 4px;"
                "  padding: 2px 10px;"
                "  font-weight: 700;"
                "  font-size: 11px;"
                "}"
            ) % (self.active_color, self.active_color)
        else:
            style = (
                "QToolButton {"
                "  background-color: #202227;"
                "  color: #A0AAB8;"
                "  border: 1px solid #363C46;"
                "  border-radius: 4px;"
                "  padding: 2px 10px;"
                "  font-weight: 500;"
                "  font-size: 11px;"
                "}"
                "QToolButton:hover {"
                "  background-color: #2D323B;"
                "  color: #FFFFFF;"
                "  border-color: #4C5563;"
                "}"
            )
        self.setStyleSheet(style)


# ===========================================================================
# Global Log Viewer Widget
# ===========================================================================

class GlobalLogViewer(QtWidgets.QWidget):
    """Centralized, filterable real-time log viewer widget."""

    def __init__(self, parent=None, initial_source=None):
        super(GlobalLogViewer, self).__init__(parent)
        self._store = log_store()
        self._active_level = "all"
        self._active_source = initial_source or "all"
        self._search_query = ""
        self._auto_scroll = True
        self._subscribed = False

        self._build_ui()
        self._connect_signals()
        self._subscribe_store()
        self.refresh()

    def _build_ui(self):
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(8)

        # 1. Top Section Panel: Filters & Search ------------------------
        from . import create_section_panel, configure_field, create_button

        panel, panel_layout, _ = create_section_panel("Filters & Search", accent="pipeline", parent=self)

        # Row 1: Tool Source + Filter Search Field
        row1 = QtWidgets.QHBoxLayout()
        row1.setSpacing(INLINE_SPACING)

        src_lbl = QtWidgets.QLabel("Tool Source")
        src_lbl.setObjectName("FieldLabel")
        src_lbl.setFixedWidth(FORM_LABEL_WIDTH)

        self.source_combo = QtWidgets.QComboBox()
        self.source_combo.setMinimumWidth(160)
        configure_field(self.source_combo)
        self.source_combo.addItem("All Tools", "all")
        self.source_combo.addItem("UDIM Manager", "UDIM Manager")
        self.source_combo.addItem("Shader Tools", "Shader Tools")
        self.source_combo.addItem("Renamer", "Renamer")
        self.source_combo.addItem("Skin Tools", "Skin Tools")
        self.source_combo.addItem("Model Sanitizer", "Model Sanitizer")
        self.source_combo.addItem("Character Finalizer", "Character Finalizer")
        self.source_combo.addItem("Licensing", "Licensing")

        search_lbl = QtWidgets.QLabel("Filter")
        search_lbl.setObjectName("FieldLabel")
        search_lbl.setFixedWidth(40)

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Search logs / keywords...")
        self.search_input.setClearButtonEnabled(True)
        configure_field(self.search_input)

        row1.addWidget(src_lbl)
        row1.addWidget(self.source_combo)
        row1.addWidget(search_lbl)
        row1.addWidget(self.search_input, 1)
        panel_layout.addLayout(row1)

        # Row 2: Filter Chip Badges + Clear Button
        row2 = QtWidgets.QHBoxLayout()
        row2.setSpacing(6)

        self.chip_all = FilterChipButton("All", "all", COLOR_CHIP_ALL_ACTIVE, self)
        self.chip_error = FilterChipButton("Errors", LEVEL_ERROR, COLOR_CHIP_ERROR_ACTIVE, self)
        self.chip_warning = FilterChipButton("Warnings", LEVEL_WARNING, COLOR_CHIP_WARNING_ACTIVE, self)
        self.chip_success = FilterChipButton("Success", LEVEL_SUCCESS, COLOR_CHIP_SUCCESS_ACTIVE, self)
        self.chip_info = FilterChipButton("Info", LEVEL_INFO, COLOR_CHIP_INFO_ACTIVE, self)

        self.chip_group = QtWidgets.QButtonGroup(self)
        self.chip_group.setExclusive(True)
        self.chip_group.addButton(self.chip_all)
        self.chip_group.addButton(self.chip_error)
        self.chip_group.addButton(self.chip_warning)
        self.chip_group.addButton(self.chip_success)
        self.chip_group.addButton(self.chip_info)
        self.chip_all.setChecked(True)

        row2.addWidget(self.chip_all)
        row2.addWidget(self.chip_error)
        row2.addWidget(self.chip_warning)
        row2.addWidget(self.chip_success)
        row2.addWidget(self.chip_info)
        row2.addStretch(1)

        self.clear_logs_btn = create_button("Clear", role="secondary", fixed_width=70, parent=self)
        row2.addWidget(self.clear_logs_btn)

        panel_layout.addLayout(row2)
        root_layout.addWidget(panel)

        # 2. Main Console Output Display -------------------------------
        self.console_view = QtWidgets.QTextBrowser(self)
        self.console_view.setObjectName("ConsoleView")
        self.console_view.setReadOnly(True)
        self.console_view.setOpenExternalLinks(False)
        root_layout.addWidget(self.console_view, 1)

        # 3. Bottom Action & Status Bar --------------------------------
        from .controls import create_toggle_switch

        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.setSpacing(INLINE_SPACING)

        self.autoscroll_toggle = create_toggle_switch("Auto-scroll", checked=True, accent="pipeline", parent=self)

        self.match_count_label = QtWidgets.QLabel("0 message(s)", self)
        self.match_count_label.setObjectName("LogCountBadge")

        self.copy_btn = create_button("Copy All", role="secondary", fixed_width=85, parent=self)
        self.export_btn = create_button("Export Log...", role="secondary", fixed_width=100, parent=self)

        bottom_layout.addWidget(self.autoscroll_toggle)
        bottom_layout.addWidget(self.match_count_label)
        bottom_layout.addStretch(1)
        bottom_layout.addWidget(self.copy_btn)
        bottom_layout.addWidget(self.export_btn)
        root_layout.addLayout(bottom_layout)

    def _connect_signals(self):
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.search_input.textChanged.connect(self._on_search_changed)
        self.chip_group.buttonClicked.connect(self._on_chip_clicked)
        self.clear_logs_btn.clicked.connect(self._on_clear_clicked)
        self.copy_btn.clicked.connect(self._on_copy_clicked)
        self.export_btn.clicked.connect(self._on_export_clicked)
        self.autoscroll_toggle.toggled.connect(self._on_autoscroll_toggled)

    def _subscribe_store(self):
        if not self._subscribed:
            self._store.subscribe(self._on_store_event)
            self._subscribed = True

    def closeEvent(self, event):
        self._store.unsubscribe(self._on_store_event)
        self._subscribed = False
        super(GlobalLogViewer, self).closeEvent(event)

    def set_active_source(self, source_name):
        if not source_name:
            self.source_combo.setCurrentIndex(0)
            return
        idx = self.source_combo.findData(source_name)
        if idx >= 0:
            self.source_combo.setCurrentIndex(idx)
        else:
            text_idx = self.source_combo.findText(source_name)
            if text_idx >= 0:
                self.source_combo.setCurrentIndex(text_idx)
            else:
                self.source_combo.addItem(source_name, source_name)
                self.source_combo.setCurrentIndex(self.source_combo.count() - 1)

    def _on_source_changed(self, index):
        self._active_source = str(self.source_combo.itemData(index) or "all")
        self.refresh()

    def _on_search_changed(self, text):
        self._search_query = str(text or "").strip()
        self.refresh()

    def _on_chip_clicked(self, button):
        self._active_level = getattr(button, "level_key", "all")
        self.refresh()

    def _on_clear_clicked(self):
        self._store.clear()
        self.refresh()

    def _on_autoscroll_toggled(self, checked):
        self._auto_scroll = bool(checked)
        if self._auto_scroll:
            scroll = self.console_view.verticalScrollBar()
            scroll.setValue(scroll.maximum())

    def _on_copy_clicked(self):
        text = self.console_view.toPlainText()
        if text:
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(text)

    def _on_export_clicked(self):
        text = self.console_view.toPlainText()
        if not text:
            return
        suggested = os.path.join(
            os.path.expanduser("~"),
            "scartools_log_{}.txt".format(time.strftime("%Y%m%d_%H%M%S")),
        )
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export ScarTools Diagnostic Log",
            suggested,
            "Text Files (*.txt);;All Files (*.*)",
        )
        if path:
            try:
                with open(path, "w") as f:
                    f.write(text)
            except Exception as e:
                pass

    def _on_store_event(self, *args, **kwargs):
        self.refresh()

    def _format_entry_html(self, entry):
        color_map = {
            LEVEL_INFO: "#79A9E6",
            LEVEL_SUCCESS: "#72D6AA",
            LEVEL_WARNING: "#D6B36A",
            LEVEL_ERROR: "#F07D7D",
        }
        badge_bg_map = {
            LEVEL_INFO: "#1E3048",
            LEVEL_SUCCESS: "#17382B",
            LEVEL_WARNING: "#3D3019",
            LEVEL_ERROR: "#421C1C",
        }
        color = color_map.get(entry.level, "#A0A0A0")
        badge_bg = badge_bg_map.get(entry.level, "#22252A")
        ts = time.strftime("%H:%M:%S", time.localtime(entry.timestamp))

        # Sanitize HTML tags
        msg = (
            entry.message.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>&nbsp;&nbsp;&nbsp;&nbsp;")
        )

        return (
            '<div style="margin-bottom: 4px; font-family: Consolas, monospace; font-size: 11px; line-height: 1.35;">'
            '<span style="color: #6C727F;">[{time}]</span> '
            '<span style="background-color: {badge_bg}; color: {color}; font-weight: 700; padding: 1px 4px; border-radius: 3px; font-size: 9.5px;">{level}</span> '
            '<span style="color: #9CA3AF; font-weight: 600;">[{source}]</span> '
            '<span style="color: {color};">{msg}</span>'
            "</div>"
        ).format(
            time=ts,
            badge_bg=badge_bg,
            color=color,
            level=entry.level,
            source=entry.source,
            msg=msg,
        )

    def refresh(self):
        source = None if self._active_source == "all" else self._active_source
        level = None if self._active_level == "all" else self._active_level
        query = self._search_query if self._search_query else None

        entries = self._store.query(level=level, source=source, search=query)
        counts = self._store.counts(source=source)

        self.chip_all.update_count(counts["all"])
        self.chip_error.update_count(counts[LEVEL_ERROR])
        self.chip_warning.update_count(counts[LEVEL_WARNING])
        self.chip_success.update_count(counts[LEVEL_SUCCESS])
        self.chip_info.update_count(counts[LEVEL_INFO])

        self.match_count_label.setText("{} message(s)".format(len(entries)))

        html_blocks = [self._format_entry_html(e) for e in entries]
        self.console_view.setHtml("".join(html_blocks))

        if self._auto_scroll:
            scroll = self.console_view.verticalScrollBar()
            scroll.setValue(scroll.maximum())


# ===========================================================================
# Top-Level Window Dialog
# ===========================================================================

class GlobalLogWindow(BaseToolDialog):
    """Top-level, standardized ScarTools Log Viewer Window."""

    OBJECT_NAME = "ScarToolsLogViewerWindow"
    TOOL_ID = "scartools"

    def __init__(self, parent=None, initial_source=None):
        super(GlobalLogWindow, self).__init__(
            parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle("ScarTools — Log Viewer")
        
        from . import configure_window, configure_root_layout, create_brand_header
        configure_window(self, (720, 540), (840, 640))

        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Brand Header
        header, self.subtitle_lbl = create_brand_header(
            "LOG VIEWER",
            "Centralized diagnostic stream & operation events",
            parent=self,
        )
        root.addWidget(header)

        # 2. Main Viewer Widget
        self.viewer = GlobalLogViewer(self, initial_source=initial_source)
        root.addWidget(self.viewer, 1)

    def set_active_source(self, source_name):
        self.viewer.set_active_source(source_name)


_ACTIVE_GLOBAL_LOG_WINDOW = None


def show_global_log(source=None, parent=None):
    """
    Open or bring to focus the unified ScarTools Log Viewer,
    optionally setting the tool source filter.
    """
    global _ACTIVE_GLOBAL_LOG_WINDOW
    try:
        if _ACTIVE_GLOBAL_LOG_WINDOW is not None and _ACTIVE_GLOBAL_LOG_WINDOW.isVisible():
            if source:
                _ACTIVE_GLOBAL_LOG_WINDOW.set_active_source(source)
            _ACTIVE_GLOBAL_LOG_WINDOW.raise_()
            _ACTIVE_GLOBAL_LOG_WINDOW.activateWindow()
            return _ACTIVE_GLOBAL_LOG_WINDOW
    except Exception:
        _ACTIVE_GLOBAL_LOG_WINDOW = None

    window = GlobalLogWindow(parent=parent, initial_source=source)
    _ACTIVE_GLOBAL_LOG_WINDOW = window
    window.show()
    return window


class LogDialog(GlobalLogWindow):
    """Legacy backward-compatible LogDialog alias."""
    pass


__all__ = [
    "FilterChipButton",
    "GlobalLogViewer",
    "GlobalLogWindow",
    "LogDialog",
    "show_global_log",
]
