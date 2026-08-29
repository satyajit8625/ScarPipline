# -*- coding: utf-8 -*-
"""Workspace Layouts, Wizard Steps, Maya Docking & Preset Management for ScarTools."""

from __future__ import absolute_import, division, print_function

import json
import os
import sys

import maya.cmds as cmds
try:
    import maya.OpenMayaUI as omui
except Exception:
    omui = None

from .qt import QtCore, QtGui, QtWidgets, maya_main_window
from .tokens import (
    COLOR_BG_PANEL,
    COLOR_BG_INPUT,
    COLOR_PRIMARY_BLUE,
    COLOR_STATUS_SUCCESS,
    FIELD_HEIGHT,
    INLINE_SPACING,
)


# ===========================================================================
# 1. Step Wizard Progress Indicator
# ===========================================================================

class StepWizardWidget(QtWidgets.QWidget):
    """Visual pipeline step tracker (e.g. [1. Select] ➔ [2. Inspect] ➔ [3. Fix] ➔ [4. Export])."""

    stepChanged = QtCore.Signal(int)

    def __init__(self, steps=None, current=0, parent=None):
        super(StepWizardWidget, self).__init__(parent)
        self._steps = steps or ["Select", "Preflight", "Process", "Export"]
        self._current = int(current)

        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._buttons = []
        self._build_steps()

    def _build_steps(self):
        for i, title in enumerate(self._steps):
            btn = QtWidgets.QToolButton()
            btn.setObjectName("WizardStepBtn")
            btn.setText("{}. {}".format(i + 1, title))
            btn.setCheckable(True)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setFixedHeight(26)
            btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked, idx=i: self.set_current_step(idx))
            self._buttons.append(btn)
            self._layout.addWidget(btn)

            if i < len(self._steps) - 1:
                arrow = QtWidgets.QLabel("➔")
                arrow.setStyleSheet("color: #4C5564; font-size: 10px;")
                self._layout.addWidget(arrow)

        self._update_styles()

    def set_current_step(self, index):
        self._current = max(0, min(len(self._steps) - 1, int(index)))
        self._update_styles()
        self.stepChanged.emit(self._current)

    def current_step(self):
        return self._current

    def _update_styles(self):
        for i, btn in enumerate(self._buttons):
            if i == self._current:
                btn.setChecked(True)
                btn.setProperty("state", "active")
            elif i < self._current:
                btn.setChecked(False)
                btn.setProperty("state", "done")
            else:
                btn.setChecked(False)
                btn.setProperty("state", "pending")
            btn.style().unpolish(btn)
            btn.style().polish(btn)


def create_step_wizard(steps=None, current=0, parent=None):
    return StepWizardWidget(steps=steps, current=current, parent=parent)


# ===========================================================================
# 2. Centralized JSON Preset Manager
# ===========================================================================

class PresetManager(object):
    """Handles persistent JSON user presets for tools in ~/.scartools/presets/<tool_id>/."""

    def __init__(self, tool_id):
        self.tool_id = str(tool_id or "general")
        self.dir_path = os.path.join(os.path.expanduser("~"), ".scartools", "presets", self.tool_id)
        os.makedirs(self.dir_path, exist_ok=True)

    def list_presets(self):
        if not os.path.exists(self.dir_path):
            return []
        files = [f[:-5] for f in os.listdir(self.dir_path) if f.endswith(".json")]
        return sorted(files)

    def save_preset(self, name, data):
        clean_name = "".join(c for c in name if c.isalnum() or c in ("_", "-")).strip()
        if not clean_name:
            return False
        p = os.path.join(self.dir_path, clean_name + ".json")
        with open(p, "w") as fp:
            json.dump(data, fp, indent=2)
        return True

    def load_preset(self, name):
        p = os.path.join(self.dir_path, name + ".json")
        if not os.path.exists(p):
            return None
        with open(p, "r") as fp:
            return json.load(fp)

    def delete_preset(self, name):
        p = os.path.join(self.dir_path, name + ".json")
        if os.path.exists(p):
            os.remove(p)
            return True
        return False


class PresetBar(QtWidgets.QWidget):
    """Header toolbar containing preset selection, save, and manage buttons."""

    presetLoaded = QtCore.Signal(dict)
    presetSaved = QtCore.Signal(str)

    def __init__(self, tool_id, getter_fn=None, setter_fn=None, parent=None):
        super(PresetBar, self).__init__(parent)
        self.manager = PresetManager(tool_id)
        self._getter = getter_fn
        self._setter = setter_fn

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        lbl = QtWidgets.QLabel("Preset:")
        lbl.setStyleSheet("color: #8A94A6; font-size: 11px; font-weight: 600;")
        layout.addWidget(lbl)

        self.combo = QtWidgets.QComboBox()
        self.combo.setFixedHeight(24)
        self.combo.setMinimumWidth(130)
        layout.addWidget(self.combo)

        self.save_btn = QtWidgets.QToolButton()
        self.save_btn.setObjectName("PresetActionBtn")
        self.save_btn.setText("Save")
        self.save_btn.setToolTip("Save current settings to active preset")
        self.save_btn.setFixedHeight(24)
        self.save_btn.setCursor(QtCore.Qt.PointingHandCursor)
        layout.addWidget(self.save_btn)

        self.new_btn = QtWidgets.QToolButton()
        self.new_btn.setObjectName("PresetActionBtn")
        self.new_btn.setText("+ New")
        self.new_btn.setToolTip("Create a new preset profile")
        self.new_btn.setFixedHeight(24)
        self.new_btn.setCursor(QtCore.Qt.PointingHandCursor)
        layout.addWidget(self.new_btn)

        self.save_btn.clicked.connect(self._save_current)
        self.new_btn.clicked.connect(self._create_new)
        self.combo.currentIndexChanged.connect(self._on_preset_selected)

        self.refresh_presets()

    def refresh_presets(self):
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("— Select Preset —", "")
        for p in self.manager.list_presets():
            self.combo.addItem(p, p)
        self.combo.blockSignals(False)

    def _on_preset_selected(self, idx):
        name = self.combo.itemData(idx)
        if name:
            data = self.manager.load_preset(name)
            if data is not None:
                if self._setter:
                    self._setter(data)
                self.presetLoaded.emit(data)

    def _save_current(self):
        cur = self.combo.currentText().strip()
        if not cur or cur.startswith("—"):
            self._create_new()
            return
        if self._getter:
            data = self._getter()
            self.manager.save_preset(cur, data)
            self.presetSaved.emit(cur)

    def _create_new(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "New Preset", "Preset Name:")
        if ok and name.strip():
            clean = name.strip()
            data = self._getter() if self._getter else {}
            self.manager.save_preset(clean, data)
            self.refresh_presets()
            idx = self.combo.findText(clean)
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
            self.presetSaved.emit(clean)


def create_preset_bar(tool_id, getter_fn=None, setter_fn=None, parent=None):
    return PresetBar(tool_id=tool_id, getter_fn=getter_fn, setter_fn=setter_fn, parent=parent)


# ===========================================================================
# 3. Maya Native Workspace Docking Helper
# ===========================================================================

def dock_tool_window(tool_id, window_widget, title="ScarTools"):
    """Dock a ScarTools dialog inside Maya's workspaceControl interface."""
    ctrl_name = "{}_WorkspaceControl".format(tool_id)
    if cmds.workspaceControl(ctrl_name, exists=True):
        cmds.deleteUI(ctrl_name, control=True)

    ctrl = cmds.workspaceControl(
        ctrl_name,
        label=title,
        retain=False,
        floating=True,
        uiScript="",
    )
    # Reparent widget to Maya control pointer
    try:
        from shiboken2 import wrapInstance
    except ImportError:
        from shiboken6 import wrapInstance

    ptr = omui.MQtUtil.findControl(ctrl_name)
    if ptr is not None:
        parent_widget = wrapInstance(int(ptr), QtWidgets.QWidget)
        if parent_widget and hasattr(parent_widget, "layout") and parent_widget.layout():
            parent_widget.layout().addWidget(window_widget)
        window_widget.show()
    return ctrl_name


__all__ = [
    "StepWizardWidget",
    "create_step_wizard",
    "PresetManager",
    "PresetBar",
    "create_preset_bar",
    "dock_tool_window",
]
