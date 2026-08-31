# -*- coding: utf-8 -*-
"""
Dedicated Studio Settings Architecture for Anim Export (Alembic & FBX Parameters).
Consolidates all settings into a single master department card using 100% centralized components.
"""

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
    create_collapsible_card,
    create_badge,
    apply_theme,
    repolish,
    PRIMARY_BUTTON_WIDTH,
    SECONDARY_BUTTON_MIN_WIDTH,
)
from scartools.ui.controls import (
    create_toggle_switch,
    create_segmented_control,
)


DEFAULT_SETTINGS = {
    "preset": "Pipeline Default",
    # Alembic Parameters
    "alembic": {
        "data_format": "ogawa",
        "step": 1.0,
        "handles": 0,
        "uvs": True,
        "normals": True,
        "visibility": True,
        "face_sets": True,
        "color_sets": False,
        "world_space": True,
        "strip_namespaces": True,
        "write_velocities": True,
        "renderable_only": True,
        "whole_frame_geo": False,
        "write_creases": True,
        "euler_filter": False,
    },
    # FBX Parameters
    "fbx": {
        "animation": True,
        "bake_animation": True,
        "step": 1.0,
        "resample": True,
        "skin": True,
        "blend_shapes": True,
        "smoothing_groups": True,
        "tangents_binormals": True,
        "triangulate": False,
        "cameras": True,
        "lights": False,
        "embed_media": False,
        "format": "binary",
        "up_axis": "Y-Up",
        "fbx_version": "FBX 2020",
        "euler_filter": False,
        "constant_key_reducer": False,
        "preserve_instances": False,
    },
}

SETTINGS_KEY = "anim_export_settings"


def get_anim_export_settings():
    """Retrieve persistent settings dict with studio defaults fallback."""
    data = settings.get_json(SETTINGS_KEY, {}) or {}
    res = {
        "preset": data.get("preset", DEFAULT_SETTINGS["preset"]),
        "alembic": dict(DEFAULT_SETTINGS["alembic"]),
        "fbx": dict(DEFAULT_SETTINGS["fbx"]),
    }
    if isinstance(data.get("alembic"), dict):
        res["alembic"].update(data["alembic"])
    if isinstance(data.get("fbx"), dict):
        res["fbx"].update(data["fbx"])
    return res


def save_anim_export_settings(data):
    """Persist settings dictionary into Maya optionVar store."""
    current = get_anim_export_settings()
    if "alembic" in data and isinstance(data["alembic"], dict):
        current["alembic"].update(data["alembic"])
    if "fbx" in data and isinstance(data["fbx"], dict):
        current["fbx"].update(data["fbx"])
    if "preset" in data:
        current["preset"] = data["preset"]
    settings.set_json(SETTINGS_KEY, current)
    return current


def reset_anim_export_settings():
    """Restore all parameters to studio pipeline defaults."""
    settings.set_json(SETTINGS_KEY, DEFAULT_SETTINGS)
    return {
        "preset": DEFAULT_SETTINGS["preset"],
        "alembic": dict(DEFAULT_SETTINGS["alembic"]),
        "fbx": dict(DEFAULT_SETTINGS["fbx"]),
    }


def confirm_and_reset_settings(parent=None):
    """Show modal confirmation before restoring ScarTools pipeline defaults."""
    dialog = QtWidgets.QDialog(parent if parent is not None else maya_main_window())
    dialog.setWindowTitle("Reset Anim Export Settings?")
    dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
    dialog.setFixedWidth(380)
    apply_theme(dialog)

    root = QtWidgets.QVBoxLayout(dialog)
    root.setContentsMargins(18, 18, 18, 18)
    root.setSpacing(14)

    title_lbl = QtWidgets.QLabel("Reset Anim Export Settings?")
    title_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #FFFFFF;")
    root.addWidget(title_lbl)

    msg_lbl = QtWidgets.QLabel(
        "This restores the ScarTools pipeline defaults for FBX and Alembic shot export.\n\nAre you sure you want to proceed?"
    )
    msg_lbl.setWordWrap(True)
    msg_lbl.setStyleSheet("color: #C0C0C0; font-size: 11px;")
    root.addWidget(msg_lbl)

    btn_row = QtWidgets.QHBoxLayout()
    btn_row.addStretch(1)
    cancel_btn = create_button("Cancel", role="secondary", fixed_width=80, parent=dialog)
    reset_btn = create_button("Reset to Defaults", role="primary", fixed_width=130, parent=dialog)

    cancel_btn.clicked.connect(dialog.reject)
    reset_btn.clicked.connect(dialog.accept)

    btn_row.addWidget(cancel_btn)
    btn_row.addWidget(reset_btn)
    root.addLayout(btn_row)

    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        reset_anim_export_settings()
        return True
    return False


def _create_separator():
    """Create a subtle horizontal divider for single-card layouts."""
    sep = QtWidgets.QFrame()
    sep.setFrameShape(QtWidgets.QFrame.HLine)
    sep.setFrameShadow(QtWidgets.QFrame.Sunken)
    sep.setStyleSheet("border: none; border-top: 1px solid #333740; margin: 4px 0;")
    return sep


# ==============================================================================
# 🎬 Dedicated Alembic Settings Dialog (Single Master Card Architecture)
# ==============================================================================

class AlembicSettingsDialog(BaseToolDialog):
    """Dedicated Alembic Point Cache Export Configuration Dialog."""

    OBJECT_NAME = "ScarToolsAlembicSettingsDialog"
    TOOL_ID = "scartools_anim_io_alembic_settings"
    WINDOW_TITLE = "Alembic Settings"

    def __init__(self, parent=None):
        super(AlembicSettingsDialog, self).__init__(
            parent=parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        configure_window(self, (520, 520), (600, 600))

        self._current_settings = get_anim_export_settings()["alembic"]
        self._build_ui()
        self._load_values(self._current_settings)
        apply_theme(self)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Standard Brand Header [UI-02]
        header, _ = create_brand_header(
            "ALEMBIC SETTINGS",
            "Geometry cache export settings",
            parent=self,
        )
        root.addWidget(header)

        # 2. Preset Selection Bar
        preset_bar = QtWidgets.QHBoxLayout()
        preset_bar.setContentsMargins(4, 0, 4, 0)
        lbl_pre = QtWidgets.QLabel("Preset:", self)
        lbl_pre.setObjectName("SettingsFieldLabel")
        self.combo_preset = QtWidgets.QComboBox(self)
        self.combo_preset.addItems(["ScarFall Shot Cache (Default)", "Custom"])
        configure_field(self.combo_preset, minimum_width=220)
        preset_bar.addWidget(lbl_pre)
        preset_bar.addWidget(self.combo_preset)
        preset_bar.addStretch(1)
        root.addLayout(preset_bar)

        # 3. Unified Single Master Card [UI-03, FW-07]
        master_panel, layout, _ = create_section_panel("Alembic Cache Parameters", accent="pipeline", parent=self)
        layout.setSpacing(9)

        # Cache & Timing Rows
        row_fmt = QtWidgets.QHBoxLayout()
        lbl_fmt = QtWidgets.QLabel("Data Format:", self)
        lbl_fmt.setObjectName("SettingsMutedLabel")
        val_fmt = create_badge("Ogawa 🔒", variant="pipeline", parent=self)
        val_fmt.setToolTip("Ogawa is the high-performance pipeline standard for Alembic caching")
        row_fmt.addWidget(lbl_fmt)
        row_fmt.addWidget(val_fmt)
        row_fmt.addStretch(1)
        layout.addLayout(row_fmt)

        row_step = QtWidgets.QHBoxLayout()
        lbl_step = QtWidgets.QLabel("Frame Step:", self)
        lbl_step.setObjectName("SettingsMutedLabel")
        self.seg_step = create_segmented_control(["1.0 (Standard)", "0.5 (2x FX)", "0.25 (4x FX)"], current=0, accent="pipeline", parent=self)
        row_step.addWidget(lbl_step)
        row_step.addWidget(self.seg_step, 1)
        layout.addLayout(row_step)

        row_handles = QtWidgets.QHBoxLayout()
        lbl_handles = QtWidgets.QLabel("Simulation Handles:", self)
        lbl_handles.setObjectName("SettingsMutedLabel")
        self.combo_handles = QtWidgets.QComboBox(self)
        self.combo_handles.addItems(["0 Frames (Exact Shot)", "2 Frames", "5 Frames", "8 Frames", "10 Frames"])
        configure_field(self.combo_handles, minimum_width=180)
        row_handles.addWidget(lbl_handles)
        row_handles.addWidget(self.combo_handles)
        row_handles.addStretch(1)
        layout.addLayout(row_handles)

        layout.addWidget(_create_separator())

        # Geometry & Shading Flags
        grid_geo = QtWidgets.QGridLayout()
        grid_geo.setHorizontalSpacing(18)
        grid_geo.setVerticalSpacing(7)

        lbl_uv = QtWidgets.QLabel("UV Sets", self)
        lbl_uv.setToolTip("Export UV sets into Alembic (-uvWrite)")
        self.sw_uv = create_toggle_switch(text="", checked=True, accent="modeling", parent=self)

        lbl_norm = QtWidgets.QLabel("Vertex Normals", self)
        lbl_norm.setToolTip("Preserve smooth shading & custom vertex normals (-writeNormals)")
        self.sw_norm = create_toggle_switch(text="", checked=True, accent="modeling", parent=self)

        lbl_vis = QtWidgets.QLabel("Visibility Keys", self)
        lbl_vis.setToolTip("Export animation visibility channels (-writeVisibility)")
        self.sw_vis = create_toggle_switch(text="", checked=True, accent="modeling", parent=self)

        lbl_face = QtWidgets.QLabel("Face Sets (Materials)", self)
        lbl_face.setToolTip("Preserve per-face material assignments (-writeFaceSets)")
        self.sw_face = create_toggle_switch(text="", checked=True, accent="modeling", parent=self)

        lbl_col = QtWidgets.QLabel("Color Sets (Vertex Color)", self)
        lbl_col.setToolTip("Export vertex color streams (-writeColorSets)")
        self.sw_col = create_toggle_switch(text="", checked=False, accent="modeling", parent=self)

        grid_geo.addWidget(lbl_uv, 0, 0)
        grid_geo.addWidget(self.sw_uv, 0, 1)
        grid_geo.addWidget(lbl_norm, 0, 2)
        grid_geo.addWidget(self.sw_norm, 0, 3)

        grid_geo.addWidget(lbl_vis, 1, 0)
        grid_geo.addWidget(self.sw_vis, 1, 1)
        grid_geo.addWidget(lbl_face, 1, 2)
        grid_geo.addWidget(self.sw_face, 1, 3)

        grid_geo.addWidget(lbl_col, 2, 0)
        grid_geo.addWidget(self.sw_col, 2, 1)
        layout.addLayout(grid_geo)

        layout.addWidget(_create_separator())

        # Transforms & Naming
        row_tf = QtWidgets.QHBoxLayout()
        lbl_ws = QtWidgets.QLabel("World Space Matrix", self)
        lbl_ws.setToolTip("Bake world space transforms for cinematic cache exchange (-worldSpace)")
        self.sw_ws = create_toggle_switch(text="", checked=True, accent="rig", parent=self)

        lbl_strip = QtWidgets.QLabel("Strip Namespaces", self)
        lbl_strip.setToolTip("Clean namespace prefixes for downstream DCCs (-stripNamespaces)")
        self.sw_strip = create_toggle_switch(text="", checked=True, accent="rig", parent=self)

        row_tf.addWidget(lbl_ws)
        row_tf.addWidget(self.sw_ws)
        row_tf.addSpacing(20)
        row_tf.addWidget(lbl_strip)
        row_tf.addWidget(self.sw_strip)
        row_tf.addStretch(1)
        layout.addLayout(row_tf)

        layout.addWidget(_create_separator())

        # Centralized CollapsibleCard Accordion Section
        self.adv_card = create_collapsible_card("Advanced Options (Rarely Modified)", count=5, collapsed=True, parent=self)

        grid_adv = QtWidgets.QGridLayout()
        grid_adv.setHorizontalSpacing(18)
        grid_adv.setVerticalSpacing(6)

        lbl_vel = QtWidgets.QLabel("Motion Blur Velocities", self)
        lbl_vel.setToolTip("Calculate and write velocity vectors for sub-frame motion blur (-writeVelocities)")
        self.sw_vel = create_toggle_switch(text="", checked=True, accent="pipeline", parent=self)

        lbl_rend = QtWidgets.QLabel("Renderable Only", self)
        lbl_rend.setToolTip("Skip hidden utility rigs and locators (-renderableOnly)")
        self.sw_rend = create_toggle_switch(text="", checked=True, accent="pipeline", parent=self)

        lbl_crease = QtWidgets.QLabel("Subd Creases", self)
        lbl_crease.setToolTip("Preserve edge/vertex crease weights (-writeCreases)")
        self.sw_crease = create_toggle_switch(text="", checked=True, accent="modeling", parent=self)

        lbl_whole = QtWidgets.QLabel("Whole Frame Geometry", self)
        lbl_whole.setToolTip("Export whole frame geometry topology")
        self.sw_whole = create_toggle_switch(text="", checked=False, accent="modeling", parent=self)

        lbl_euler = QtWidgets.QLabel("Euler Filter", self)
        lbl_euler.setToolTip("Apply gimbal-lock angle filter (-eulerFilter)")
        self.sw_euler = create_toggle_switch(text="", checked=False, accent="rig", parent=self)

        grid_adv.addWidget(lbl_vel, 0, 0)
        grid_adv.addWidget(self.sw_vel, 0, 1)
        grid_adv.addWidget(lbl_rend, 0, 2)
        grid_adv.addWidget(self.sw_rend, 0, 3)

        grid_adv.addWidget(lbl_crease, 1, 0)
        grid_adv.addWidget(self.sw_crease, 1, 1)
        grid_adv.addWidget(lbl_whole, 1, 2)
        grid_adv.addWidget(self.sw_whole, 1, 3)

        grid_adv.addWidget(lbl_euler, 2, 0)
        grid_adv.addWidget(self.sw_euler, 2, 1)

        self.adv_card.add_layout(grid_adv)
        layout.addWidget(self.adv_card)

        root.addWidget(master_panel)

        # 4. Standard Action Footer [UI-06]
        footer_frame = QtWidgets.QFrame(self)
        footer_frame.setObjectName("ActionFooter")
        footer_layout = QtWidgets.QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(10, 8, 10, 8)
        footer_layout.setSpacing(10)

        self.btn_reset = create_button("↺ Reset to Default", role="secondary", parent=self)
        self.btn_cancel = create_button("Cancel", role="secondary", fixed_width=90, parent=self)
        self.btn_save = create_button("Save Settings", role="primary", fixed_width=140, parent=self)

        footer_layout.addWidget(self.btn_reset)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.btn_cancel)
        footer_layout.addWidget(self.btn_save)
        root.addWidget(footer_frame)

        # Connections
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_cancel.clicked.connect(self.close)
        self.btn_save.clicked.connect(self._on_save)

    def _load_values(self, data):
        step_val = float(data.get("step", 1.0))
        self.seg_step.set_current_index(0 if step_val >= 1.0 else (1 if step_val >= 0.5 else 2))

        handles_map = {0: 0, 2: 1, 5: 2, 8: 3, 10: 4}
        h_val = int(data.get("handles", 0))
        self.combo_handles.setCurrentIndex(handles_map.get(h_val, 0))

        self.sw_uv.set_checked(data.get("uvs", True))
        self.sw_norm.set_checked(data.get("normals", True))
        self.sw_vis.set_checked(data.get("visibility", True))
        self.sw_face.set_checked(data.get("face_sets", True))
        self.sw_col.set_checked(data.get("color_sets", False))
        self.sw_ws.set_checked(data.get("world_space", True))
        self.sw_strip.set_checked(data.get("strip_namespaces", True))

        self.sw_vel.set_checked(data.get("write_velocities", True))
        self.sw_rend.set_checked(data.get("renderable_only", True))
        self.sw_crease.set_checked(data.get("write_creases", True))
        self.sw_whole.set_checked(data.get("whole_frame_geo", False))
        self.sw_euler.set_checked(data.get("euler_filter", False))

    def _collect_values(self):
        step_map = [1.0, 0.5, 0.25]
        handles_map = [0, 2, 5, 8, 10]
        step_idx = self.seg_step.current_index()
        h_idx = self.combo_handles.currentIndex()

        return {
            "data_format": "ogawa",
            "step": step_map[step_idx] if step_idx < len(step_map) else 1.0,
            "handles": handles_map[h_idx] if h_idx < len(handles_map) else 0,
            "uvs": self.sw_uv.is_checked(),
            "normals": self.sw_norm.is_checked(),
            "visibility": self.sw_vis.is_checked(),
            "face_sets": self.sw_face.is_checked(),
            "color_sets": self.sw_col.is_checked(),
            "world_space": self.sw_ws.is_checked(),
            "strip_namespaces": self.sw_strip.is_checked(),
            "write_velocities": self.sw_vel.is_checked(),
            "renderable_only": self.sw_rend.is_checked(),
            "write_creases": self.sw_crease.is_checked(),
            "whole_frame_geo": self.sw_whole.is_checked(),
            "euler_filter": self.sw_euler.is_checked(),
        }

    def _on_reset(self):
        if confirm_and_reset_settings(parent=self):
            defaults = get_anim_export_settings()["alembic"]
            self._load_values(defaults)

    def _on_save(self):
        data = self._collect_values()
        save_anim_export_settings({"alembic": data})
        self.accept()


# ==============================================================================
# 🎮 Dedicated FBX Settings Dialog (Single Master Card Architecture)
# ==============================================================================

class FBXSettingsDialog(BaseToolDialog):
    """Dedicated FBX Animation Take Export Configuration Dialog."""

    OBJECT_NAME = "ScarToolsFBXSettingsDialog"
    TOOL_ID = "scartools_anim_io_fbx_settings"
    WINDOW_TITLE = "FBX Settings"

    def __init__(self, parent=None):
        super(FBXSettingsDialog, self).__init__(
            parent=parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        configure_window(self, (520, 520), (600, 600))

        self._current_settings = get_anim_export_settings()["fbx"]
        self._build_ui()
        self._load_values(self._current_settings)
        apply_theme(self)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Standard Brand Header [UI-02]
        header, _ = create_brand_header(
            "FBX SETTINGS",
            "Animation and scene export settings",
            parent=self,
        )
        root.addWidget(header)

        # 2. Preset Selection Bar
        preset_bar = QtWidgets.QHBoxLayout()
        preset_bar.setContentsMargins(4, 0, 4, 0)
        lbl_pre = QtWidgets.QLabel("Preset:", self)
        lbl_pre.setObjectName("SettingsFieldLabel")
        self.combo_preset = QtWidgets.QComboBox(self)
        self.combo_preset.addItems(["ScarFall Shot Cache (Default)", "Custom"])
        configure_field(self.combo_preset, minimum_width=220)
        preset_bar.addWidget(lbl_pre)
        preset_bar.addWidget(self.combo_preset)
        preset_bar.addStretch(1)
        root.addLayout(preset_bar)

        # 3. Unified Single Master Card [UI-03, FW-07]
        master_panel, layout, _ = create_section_panel("FBX Export Configuration", accent="rig", parent=self)
        layout.setSpacing(9)

        # Animation & Deformation Grid
        grid_anim = QtWidgets.QGridLayout()
        grid_anim.setHorizontalSpacing(18)
        grid_anim.setVerticalSpacing(7)

        lbl_anim = QtWidgets.QLabel("Animation Takes", self)
        lbl_anim.setToolTip("Export keyframe animation takes")
        self.sw_anim = create_toggle_switch(text="", checked=True, accent="rig", parent=self)

        lbl_bake = QtWidgets.QLabel("Bake Animation", self)
        lbl_bake.setToolTip("Bake complex animation & constraints down to keys")
        self.sw_bake = create_toggle_switch(text="", checked=True, accent="rig", parent=self)

        lbl_resample = QtWidgets.QLabel("Resample Curves", self)
        lbl_resample.setToolTip("Resample animation curves per frame")
        self.sw_resample = create_toggle_switch(text="", checked=True, accent="rig", parent=self)

        lbl_skin = QtWidgets.QLabel("Skin Weights", self)
        lbl_skin.setToolTip("Export smooth skin cluster deforming influences")
        self.sw_skin = create_toggle_switch(text="", checked=True, accent="rig", parent=self)

        lbl_blend = QtWidgets.QLabel("Blend Shapes", self)
        lbl_blend.setToolTip("Export blendshape target channels")
        self.sw_blend = create_toggle_switch(text="", checked=True, accent="rig", parent=self)

        grid_anim.addWidget(lbl_anim, 0, 0)
        grid_anim.addWidget(self.sw_anim, 0, 1)
        grid_anim.addWidget(lbl_bake, 0, 2)
        grid_anim.addWidget(self.sw_bake, 0, 3)

        grid_anim.addWidget(lbl_resample, 1, 0)
        grid_anim.addWidget(self.sw_resample, 1, 1)
        grid_anim.addWidget(lbl_skin, 1, 2)
        grid_anim.addWidget(self.sw_skin, 1, 3)

        grid_anim.addWidget(lbl_blend, 2, 0)
        grid_anim.addWidget(self.sw_blend, 2, 1)
        layout.addLayout(grid_anim)

        layout.addWidget(_create_separator())

        # Geometry & Scene Data Grid
        grid_geo = QtWidgets.QGridLayout()
        grid_geo.setHorizontalSpacing(18)
        grid_geo.setVerticalSpacing(7)

        lbl_smooth = QtWidgets.QLabel("Smoothing Groups", self)
        lbl_smooth.setToolTip("Export polygon smoothing groups")
        self.sw_smooth = create_toggle_switch(text="", checked=True, accent="modeling", parent=self)

        lbl_tangents = QtWidgets.QLabel("Tangents / Binormals", self)
        lbl_tangents.setToolTip("Compute and export normal map tangent vectors")
        self.sw_tangents = create_toggle_switch(text="", checked=True, accent="modeling", parent=self)

        lbl_tri = QtWidgets.QLabel("Triangulate Polygons", self)
        lbl_tri.setToolTip("Force triangulation of non-planar polygons")
        self.sw_tri = create_toggle_switch(text="", checked=False, accent="modeling", parent=self)

        lbl_cam = QtWidgets.QLabel("Cameras", self)
        lbl_cam.setToolTip("Include shot cameras in FBX take")
        self.sw_cam = create_toggle_switch(text="", checked=True, accent="pipeline", parent=self)

        lbl_light = QtWidgets.QLabel("Lights", self)
        lbl_light.setToolTip("Include Maya scene lights")
        self.sw_light = create_toggle_switch(text="", checked=False, accent="modeling", parent=self)

        grid_geo.addWidget(lbl_smooth, 0, 0)
        grid_geo.addWidget(self.sw_smooth, 0, 1)
        grid_geo.addWidget(lbl_tangents, 0, 2)
        grid_geo.addWidget(self.sw_tangents, 0, 3)

        grid_geo.addWidget(lbl_tri, 1, 0)
        grid_geo.addWidget(self.sw_tri, 1, 1)
        grid_geo.addWidget(lbl_cam, 1, 2)
        grid_geo.addWidget(self.sw_cam, 1, 3)

        grid_geo.addWidget(lbl_light, 2, 0)
        grid_geo.addWidget(self.sw_light, 2, 1)
        layout.addLayout(grid_geo)

        layout.addWidget(_create_separator())

        # Pipeline Standards Row
        grid_pipe = QtWidgets.QGridLayout()
        grid_pipe.setHorizontalSpacing(18)
        grid_pipe.setVerticalSpacing(6)

        lbl_p_fmt = QtWidgets.QLabel("File Format:", self)
        lbl_p_fmt.setObjectName("SettingsMutedLabel")
        val_p_fmt = create_badge("Binary 🔒", variant="locked", parent=self)

        lbl_p_axis = QtWidgets.QLabel("Up Axis:", self)
        lbl_p_axis.setObjectName("SettingsMutedLabel")
        val_p_axis = create_badge("Y-Up 🔒", variant="locked", parent=self)

        lbl_p_unit = QtWidgets.QLabel("Units:", self)
        lbl_p_unit.setObjectName("SettingsMutedLabel")
        val_p_unit = create_badge("cm 🔒", variant="locked", parent=self)

        lbl_p_media = QtWidgets.QLabel("Embed Media:", self)
        lbl_p_media.setObjectName("SettingsMutedLabel")
        val_p_media = create_badge("OFF 🔒", variant="locked", parent=self)

        grid_pipe.addWidget(lbl_p_fmt, 0, 0)
        grid_pipe.addWidget(val_p_fmt, 0, 1)
        grid_pipe.addWidget(lbl_p_axis, 0, 2)
        grid_pipe.addWidget(val_p_axis, 0, 3)

        grid_pipe.addWidget(lbl_p_unit, 1, 0)
        grid_pipe.addWidget(val_p_unit, 1, 1)
        grid_pipe.addWidget(lbl_p_media, 1, 2)
        grid_pipe.addWidget(val_p_media, 1, 3)
        layout.addLayout(grid_pipe)

        layout.addWidget(_create_separator())

        # Centralized CollapsibleCard Accordion Section
        self.adv_card = create_collapsible_card("Advanced Options (Rarely Modified)", count=3, collapsed=True, parent=self)

        grid_adv = QtWidgets.QGridLayout()
        grid_adv.setHorizontalSpacing(18)
        grid_adv.setVerticalSpacing(6)

        lbl_euler = QtWidgets.QLabel("Euler Filter", self)
        lbl_euler.setToolTip("Apply rotation curve gimbal filter")
        self.sw_euler = create_toggle_switch(text="", checked=False, accent="rig", parent=self)

        lbl_ckr = QtWidgets.QLabel("Constant Key Reducer", self)
        lbl_ckr.setToolTip("Prune redundant constant keyframes")
        self.sw_ckr = create_toggle_switch(text="", checked=False, accent="rig", parent=self)

        lbl_pres = QtWidgets.QLabel("Preserve Instances", self)
        lbl_pres.setToolTip("Preserve geometry instancing")
        self.sw_pres = create_toggle_switch(text="", checked=False, accent="modeling", parent=self)

        grid_adv.addWidget(lbl_euler, 0, 0)
        grid_adv.addWidget(self.sw_euler, 0, 1)
        grid_adv.addWidget(lbl_ckr, 0, 2)
        grid_adv.addWidget(self.sw_ckr, 0, 3)
        grid_adv.addWidget(lbl_pres, 1, 0)
        grid_adv.addWidget(self.sw_pres, 1, 1)

        self.adv_card.add_layout(grid_adv)
        layout.addWidget(self.adv_card)

        root.addWidget(master_panel)

        # 4. Standard Action Footer [UI-06]
        footer_frame = QtWidgets.QFrame(self)
        footer_frame.setObjectName("ActionFooter")
        footer_layout = QtWidgets.QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(10, 8, 10, 8)
        footer_layout.setSpacing(10)

        self.btn_reset = create_button("↺ Reset to Default", role="secondary", parent=self)
        self.btn_cancel = create_button("Cancel", role="secondary", fixed_width=90, parent=self)
        self.btn_save = create_button("Save Settings", role="primary", fixed_width=140, parent=self)

        footer_layout.addWidget(self.btn_reset)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.btn_cancel)
        footer_layout.addWidget(self.btn_save)
        root.addWidget(footer_frame)

        # Connections
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_cancel.clicked.connect(self.close)
        self.btn_save.clicked.connect(self._on_save)

    def _load_values(self, data):
        self.sw_anim.set_checked(data.get("animation", True))
        self.sw_bake.set_checked(data.get("bake_animation", True))
        self.sw_resample.set_checked(data.get("resample", True))
        self.sw_skin.set_checked(data.get("skin", True))
        self.sw_blend.set_checked(data.get("blend_shapes", True))

        self.sw_smooth.set_checked(data.get("smoothing_groups", True))
        self.sw_tangents.set_checked(data.get("tangents_binormals", True))
        self.sw_tri.set_checked(data.get("triangulate", False))
        self.sw_cam.set_checked(data.get("cameras", True))
        self.sw_light.set_checked(data.get("lights", False))

        self.sw_euler.set_checked(data.get("euler_filter", False))
        self.sw_ckr.set_checked(data.get("constant_key_reducer", False))
        self.sw_pres.set_checked(data.get("preserve_instances", False))

    def _collect_values(self):
        return {
            "animation": self.sw_anim.is_checked(),
            "bake_animation": self.sw_bake.is_checked(),
            "step": 1.0,
            "resample": self.sw_resample.is_checked(),
            "skin": self.sw_skin.is_checked(),
            "blend_shapes": self.sw_blend.is_checked(),
            "smoothing_groups": self.sw_smooth.is_checked(),
            "tangents_binormals": self.sw_tangents.is_checked(),
            "triangulate": self.sw_tri.is_checked(),
            "cameras": self.sw_cam.is_checked(),
            "lights": self.sw_light.is_checked(),
            "embed_media": False,
            "format": "binary",
            "up_axis": "Y-Up",
            "fbx_version": "FBX 2020",
            "euler_filter": self.sw_euler.is_checked(),
            "constant_key_reducer": self.sw_ckr.is_checked(),
            "preserve_instances": self.sw_pres.is_checked(),
        }

    def _on_reset(self):
        if confirm_and_reset_settings(parent=self):
            defaults = get_anim_export_settings()["fbx"]
            self._load_values(defaults)

    def _on_save(self):
        data = self._collect_values()
        save_anim_export_settings({"fbx": data})
        self.accept()


# ==============================================================================
# Global Launchers
# ==============================================================================

_ACTIVE_ALEMBIC_DIALOG = None
_ACTIVE_FBX_DIALOG = None


def show_alembic_settings(parent=None):
    """Singleton launcher for Alembic Settings dialog."""
    global _ACTIVE_ALEMBIC_DIALOG
    if _ACTIVE_ALEMBIC_DIALOG is not None:
        try:
            _ACTIVE_ALEMBIC_DIALOG.close()
            _ACTIVE_ALEMBIC_DIALOG.deleteLater()
        except Exception:
            pass
    _ACTIVE_ALEMBIC_DIALOG = AlembicSettingsDialog(parent=parent)
    register_window("scartools_anim_io_alembic_settings", _ACTIVE_ALEMBIC_DIALOG)
    _ACTIVE_ALEMBIC_DIALOG.show()
    return _ACTIVE_ALEMBIC_DIALOG


def show_fbx_settings(parent=None):
    """Singleton launcher for FBX Settings dialog."""
    global _ACTIVE_FBX_DIALOG
    if _ACTIVE_FBX_DIALOG is not None:
        try:
            _ACTIVE_FBX_DIALOG.close()
            _ACTIVE_FBX_DIALOG.deleteLater()
        except Exception:
            pass
    _ACTIVE_FBX_DIALOG = FBXSettingsDialog(parent=parent)
    register_window("scartools_anim_io_fbx_settings", _ACTIVE_FBX_DIALOG)
    _ACTIVE_FBX_DIALOG.show()
    return _ACTIVE_FBX_DIALOG


def show_settings_dialog(parent=None, focus_section=None):
    """Compatibility launcher."""
    if focus_section == "fbx":
        return show_fbx_settings(parent=parent)
    return show_alembic_settings(parent=parent)
