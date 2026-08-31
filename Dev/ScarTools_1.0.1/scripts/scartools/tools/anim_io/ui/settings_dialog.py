# -*- coding: utf-8 -*-
"""Dedicated Studio Settings Dialog for Anim Export (Alembic & FBX Parameters)."""

from __future__ import absolute_import, division, print_function

from scartools import settings
from scartools.ui.qt import QtCore, QtWidgets, QtGui, maya_main_window
from scartools.ui.window import BaseToolDialog, register_window
from scartools.ui import (
    configure_window,
    configure_root_layout,
    configure_field,
    create_brand_header,
    create_section_panel,
    create_button,
    apply_theme,
    repolish,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_PRIMARY_BLUE,
    COLOR_ACCENT_PIPELINE,
    PRIMARY_BUTTON_WIDTH,
    SECONDARY_BUTTON_MIN_WIDTH,
)
from scartools.ui.controls import (
    create_toggle_switch,
    create_segmented_control,
)


DEFAULT_SETTINGS = {
    # Alembic Parameters
    "abc_write_velocities": True,
    "abc_step": 1.0,
    "abc_handles": 0,
    "abc_uv_write": True,
    "abc_write_normals": True,
    "abc_renderable_only": True,
    "abc_write_visibility": True,
    # FBX Parameters
    "fbx_up_axis": "Y-Up",  # "Y-Up" or "Z-Up"
    "fbx_smoothing_groups": True,
    "fbx_version": "FBX 2020",
    "fbx_triangulate": False,
}

SETTINGS_KEY = "anim_export_settings"


def get_anim_export_settings():
    """Retrieve persistent settings dict with studio defaults fallback."""
    data = settings.get_json(SETTINGS_KEY, {}) or {}
    res = dict(DEFAULT_SETTINGS)
    res.update(data)
    return res


def save_anim_export_settings(data):
    """Persist settings dictionary into Maya optionVar store."""
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    settings.set_json(SETTINGS_KEY, merged)
    return merged


def reset_anim_export_settings():
    """Restore all parameters to studio pipeline defaults."""
    settings.set_json(SETTINGS_KEY, DEFAULT_SETTINGS)
    return dict(DEFAULT_SETTINGS)


class AnimExportSettingsDialog(BaseToolDialog):
    """Studio Configuration Dialog for Alembic and FBX Caching Parameters."""

    OBJECT_NAME = "ScarToolsAnimExportSettingsDialog"
    TOOL_ID = "scartools_anim_io_settings"
    WINDOW_TITLE = "Anim Export Settings"

    def __init__(self, parent=None):
        super(AnimExportSettingsDialog, self).__init__(
            parent=parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        configure_window(self, (560, 490), (640, 580))

        self._current_settings = get_anim_export_settings()
        self._build_ui()
        self._load_values(self._current_settings)
        apply_theme(self)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Brand Header
        header, _ = create_brand_header(
            "EXPORT SETTINGS",
            "Alembic point cache and FBX animation take parameters",
            parent=self,
        )
        root.addWidget(header)

        # 2. Alembic Cache Settings Panel
        abc_panel, abc_layout, _ = create_section_panel(
            "Alembic Cache Options", accent="pipeline", parent=self
        )

        # Velocities
        vel_row = QtWidgets.QHBoxLayout()
        vel_lbl = QtWidgets.QLabel("Motion Blur Velocity Vectors (-writeVelocities)", self)
        vel_lbl.setStyleSheet("color: {};".format(COLOR_TEXT_PRIMARY))
        self.sw_abc_velocities = create_toggle_switch(text="", checked=True, accent="pipeline", parent=self)
        vel_row.addWidget(vel_lbl, 1)
        vel_row.addWidget(self.sw_abc_velocities)
        abc_layout.addLayout(vel_row)

        # Step Sampling
        step_row = QtWidgets.QHBoxLayout()
        step_lbl = QtWidgets.QLabel("Sub-Frame Sampling Step:", self)
        step_lbl.setStyleSheet("color: {};".format(COLOR_TEXT_MUTED))
        self.seg_abc_step = create_segmented_control(
            ["1.0 (Standard)", "0.5 (2x FX)", "0.25 (4x FX)"],
            current=0,
            accent="pipeline",
            parent=self,
        )
        step_row.addWidget(step_lbl)
        step_row.addWidget(self.seg_abc_step, 1)
        abc_layout.addLayout(step_row)

        # Pre-Roll Handles
        handle_row = QtWidgets.QHBoxLayout()
        handle_lbl = QtWidgets.QLabel("Pre-Roll / Simulation Handles:", self)
        handle_lbl.setStyleSheet("color: {};".format(COLOR_TEXT_MUTED))
        self.seg_abc_handles = create_segmented_control(
            ["0 Frames", "±5 Frames", "±10 Frames"],
            current=0,
            accent="pipeline",
            parent=self,
        )
        handle_row.addWidget(handle_lbl)
        handle_row.addWidget(self.seg_abc_handles, 1)
        abc_layout.addLayout(handle_row)

        # Mesh Attributes Checkboxes
        toggles_grid = QtWidgets.QGridLayout()
        toggles_grid.setHorizontalSpacing(16)
        toggles_grid.setVerticalSpacing(6)

        lbl_uv = QtWidgets.QLabel("Write UV Sets (-uvWrite)", self)
        self.sw_abc_uv = create_toggle_switch(text="", checked=True, accent="pipeline", parent=self)
        lbl_norm = QtWidgets.QLabel("Write Normals (-writeNormals)", self)
        self.sw_abc_norm = create_toggle_switch(text="", checked=True, accent="pipeline", parent=self)
        lbl_rend = QtWidgets.QLabel("Renderable Only (-renderableOnly)", self)
        self.sw_abc_rend = create_toggle_switch(text="", checked=True, accent="pipeline", parent=self)

        toggles_grid.addWidget(lbl_uv, 0, 0)
        toggles_grid.addWidget(self.sw_abc_uv, 0, 1)
        toggles_grid.addWidget(lbl_norm, 0, 2)
        toggles_grid.addWidget(self.sw_abc_norm, 0, 3)
        toggles_grid.addWidget(lbl_rend, 1, 0)
        toggles_grid.addWidget(self.sw_abc_rend, 1, 1)

        abc_layout.addLayout(toggles_grid)
        root.addWidget(abc_panel)

        # 3. FBX Export Settings Panel
        fbx_panel, fbx_layout, _ = create_section_panel(
            "FBX Export Options", accent="data", parent=self
        )

        # Up-Axis
        axis_row = QtWidgets.QHBoxLayout()
        axis_lbl = QtWidgets.QLabel("Coordinate Up-Axis:", self)
        axis_lbl.setStyleSheet("color: {};".format(COLOR_TEXT_MUTED))
        self.seg_fbx_axis = create_segmented_control(
            ["Y-Up (Maya / Film)", "Z-Up (Unreal Engine)"],
            current=0,
            accent="data",
            parent=self,
        )
        axis_row.addWidget(axis_lbl)
        axis_row.addWidget(self.seg_fbx_axis, 1)
        fbx_layout.addLayout(axis_row)

        # FBX Version & Mesh Flags
        fbx_grid = QtWidgets.QGridLayout()
        fbx_grid.setHorizontalSpacing(16)
        fbx_grid.setVerticalSpacing(6)

        lbl_ver = QtWidgets.QLabel("FBX Version:", self)
        lbl_ver.setStyleSheet("color: {};".format(COLOR_TEXT_MUTED))
        self.combo_fbx_ver = QtWidgets.QComboBox(self)
        self.combo_fbx_ver.addItems(["FBX 2020", "FBX 2018", "FBX 2016"])
        configure_field(self.combo_fbx_ver, minimum_width=120)

        lbl_smooth = QtWidgets.QLabel("Smoothing Groups", self)
        self.sw_fbx_smooth = create_toggle_switch(text="", checked=True, accent="data", parent=self)
        lbl_tri = QtWidgets.QLabel("Triangulate Polygons", self)
        self.sw_fbx_tri = create_toggle_switch(text="", checked=False, accent="data", parent=self)

        fbx_grid.addWidget(lbl_ver, 0, 0)
        fbx_grid.addWidget(self.combo_fbx_ver, 0, 1)
        fbx_grid.addWidget(lbl_smooth, 0, 2)
        fbx_grid.addWidget(self.sw_fbx_smooth, 0, 3)
        fbx_grid.addWidget(lbl_tri, 1, 2)
        fbx_grid.addWidget(self.sw_fbx_tri, 1, 3)

        fbx_layout.addLayout(fbx_grid)
        root.addWidget(fbx_panel)

        # 4. Action Buttons Footer
        footer_layout = QtWidgets.QHBoxLayout()
        footer_layout.setContentsMargins(0, 8, 0, 0)
        footer_layout.setSpacing(10)

        self.btn_reset = create_button("↺ Reset to Default", role="secondary", parent=self)
        self.btn_reset.setToolTip("Restore standard studio pipeline defaults")

        self.btn_cancel = create_button("Cancel", role="secondary", fixed_width=100, parent=self)
        self.btn_save = create_button("Save & Apply", role="primary", fixed_width=160, parent=self)

        footer_layout.addWidget(self.btn_reset)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.btn_cancel)
        footer_layout.addWidget(self.btn_save)

        root.addLayout(footer_layout)

        # Connections
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_cancel.clicked.connect(self.close)
        self.btn_save.clicked.connect(self._on_save)

    def _load_values(self, data):
        # Alembic
        self.sw_abc_velocities.set_checked(data.get("abc_write_velocities", True))
        
        step_val = float(data.get("abc_step", 1.0))
        step_idx = 0 if step_val >= 1.0 else (1 if step_val >= 0.5 else 2)
        self.seg_abc_step.set_current_index(step_idx)

        handles_val = int(data.get("abc_handles", 0))
        handles_idx = 0 if handles_val <= 0 else (1 if handles_val <= 5 else 2)
        self.seg_abc_handles.set_current_index(handles_idx)

        self.sw_abc_uv.set_checked(data.get("abc_uv_write", True))
        self.sw_abc_norm.set_checked(data.get("abc_write_normals", True))
        self.sw_abc_rend.set_checked(data.get("abc_renderable_only", True))

        # FBX
        axis_str = str(data.get("fbx_up_axis", "Y-Up"))
        self.seg_fbx_axis.set_current_index(1 if "z" in axis_str.lower() else 0)

        ver_str = str(data.get("fbx_version", "FBX 2020"))
        idx = self.combo_fbx_ver.findText(ver_str)
        if idx >= 0:
            self.combo_fbx_ver.setCurrentIndex(idx)

        self.sw_fbx_smooth.set_checked(data.get("fbx_smoothing_groups", True))
        self.sw_fbx_tri.set_checked(data.get("fbx_triangulate", False))

    def _collect_values(self):
        step_map = [1.0, 0.5, 0.25]
        handles_map = [0, 5, 10]
        axis_map = ["Y-Up", "Z-Up"]

        step_idx = self.seg_abc_step.current_index()
        handles_idx = self.seg_abc_handles.current_index()
        axis_idx = self.seg_fbx_axis.current_index()

        return {
            "abc_write_velocities": self.sw_abc_velocities.is_checked(),
            "abc_step": step_map[step_idx] if step_idx < len(step_map) else 1.0,
            "abc_handles": handles_map[handles_idx] if handles_idx < len(handles_map) else 0,
            "abc_uv_write": self.sw_abc_uv.is_checked(),
            "abc_write_normals": self.sw_abc_norm.is_checked(),
            "abc_renderable_only": self.sw_abc_rend.is_checked(),
            "abc_write_visibility": True,
            "fbx_up_axis": axis_map[axis_idx] if axis_idx < len(axis_map) else "Y-Up",
            "fbx_version": self.combo_fbx_ver.currentText(),
            "fbx_smoothing_groups": self.sw_fbx_smooth.is_checked(),
            "fbx_triangulate": self.sw_fbx_tri.is_checked(),
        }

    def _on_reset(self):
        defaults = reset_anim_export_settings()
        self._load_values(defaults)

    def _on_save(self):
        data = self._collect_values()
        save_anim_export_settings(data)
        self.accept()


_ACTIVE_SETTINGS_DIALOG = None


def show_settings_dialog(parent=None):
    """Singleton launcher for Anim Export Settings dialog."""
    global _ACTIVE_SETTINGS_DIALOG
    if _ACTIVE_SETTINGS_DIALOG is not None:
        try:
            _ACTIVE_SETTINGS_DIALOG.close()
            _ACTIVE_SETTINGS_DIALOG.deleteLater()
        except Exception:
            pass
    _ACTIVE_SETTINGS_DIALOG = AnimExportSettingsDialog(parent=parent)
    register_window("scartools_anim_io_settings", _ACTIVE_SETTINGS_DIALOG)
    _ACTIVE_SETTINGS_DIALOG.show()
    return _ACTIVE_SETTINGS_DIALOG
