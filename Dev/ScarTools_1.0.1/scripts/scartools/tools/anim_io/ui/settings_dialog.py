# -*- coding: utf-8 -*-
"""
Dedicated Compact Settings Dialogs for Anim Export (Alembic & FBX Parameters).
Exposes only creative/production options needed by artists while pipeline standards remain centralized.
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
    create_button,
    apply_theme,
    repolish,
    FORM_LABEL_WIDTH,
    INLINE_SPACING,
)
from scartools.framework.logging import emit_log


# ==============================================================================
# Central Default Settings (Single Source of Truth)
# ==============================================================================

DEFAULT_ALEMBIC_SETTINGS = {
    # Artist-configurable parameters
    "step": 1.0,
    "handles": 0,
    "uvs": True,
    "normals": True,
    "visibility": True,
    "face_sets": True,
    "color_sets": False,
    "world_space": True,
    # Hidden / Pipeline-controlled parameters
    "data_format": "ogawa",
    "write_velocities": True,
    "renderable_only": True,
    "strip_namespaces": True,
    "write_creases": True,
    "whole_frame_geo": False,
    "euler_filter": False,
}

DEFAULT_FBX_SETTINGS = {
    # Artist-configurable parameters
    "bake_animation": True,
    "step": 1,
    "resample": True,
    "euler_filter": False,
    "skin": True,
    "blend_shapes": True,
    "smoothing_groups": True,
    "cameras": True,
    # Hidden / Pipeline-controlled parameters
    "animation": True,
    "format": "binary",
    "up_axis": "Y-Up",
    "fbx_version": "FBX 2020",
    "tangents_binormals": True,
    "triangulate": False,
    "lights": False,
    "embed_media": False,
}

DEFAULT_SETTINGS = {
    "alembic": DEFAULT_ALEMBIC_SETTINGS,
    "fbx": DEFAULT_FBX_SETTINGS,
}

SETTINGS_KEY = "anim_export_settings"


# ==============================================================================
# Settings Access & Persistence API
# ==============================================================================

def get_anim_export_settings():
    """Retrieve persistent settings dict with studio defaults fallback."""
    data = settings.get_json(SETTINGS_KEY, {}) or {}
    res = {
        "alembic": dict(DEFAULT_ALEMBIC_SETTINGS),
        "fbx": dict(DEFAULT_FBX_SETTINGS),
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
    settings.set_json(SETTINGS_KEY, current)
    return current


def reset_anim_export_settings(scope="all"):
    """
    Restore parameters to studio pipeline defaults.

    Args:
        scope (str): 'alembic', 'fbx', or 'all'.
    """
    current = get_anim_export_settings()
    if scope in ("alembic", "all"):
        current["alembic"] = dict(DEFAULT_ALEMBIC_SETTINGS)
    if scope in ("fbx", "all"):
        current["fbx"] = dict(DEFAULT_FBX_SETTINGS)
    settings.set_json(SETTINGS_KEY, current)
    return current


def confirm_and_reset_settings(parent=None):
    """Show modal confirmation before restoring all ScarTools pipeline defaults."""
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
        reset_anim_export_settings(scope="all")
        emit_log("All Anim Export settings reset to studio defaults.", level="INFO", source="Anim Export")
        return True
    return False


def _create_section_header(title):
    """Create a standardized neutral section header with letter-spacing."""
    lbl = QtWidgets.QLabel(str(title).upper())
    lbl.setObjectName("SectionTitle")
    lbl.setStyleSheet("color: #8A94A6; font-size: 11px; font-weight: 600; letter-spacing: 0.8px; margin-top: 6px; margin-bottom: 2px;")
    return lbl


def _create_form_row(label_text, widget, parent=None):
    """Create a standardized form row with aligned label and control."""
    row = QtWidgets.QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(INLINE_SPACING)

    lbl = QtWidgets.QLabel(str(label_text), parent)
    lbl.setFixedWidth(110)
    lbl.setStyleSheet("color: #D2D2D2; font-size: 11px; font-weight: 500;")

    row.addWidget(lbl)
    row.addWidget(widget)
    row.addStretch(1)
    return row


# ==============================================================================
# 🎬 Dedicated Compact Alembic Settings Dialog
# ==============================================================================

class AlembicSettingsDialog(BaseToolDialog):
    """Compact Alembic Point Cache Configuration Dialog."""

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
        configure_window(self, (380, 420), (440, 480))

        self._build_ui()
        self._load_values()
        apply_theme(self)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Header
        header, _ = create_brand_header(
            "ALEMBIC SETTINGS",
            "Geometry cache export options",
            parent=self,
        )
        root.addWidget(header)

        # Main Card Panel
        card = QtWidgets.QFrame(self)
        card.setObjectName("ActionCard")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(14, 10, 14, 14)
        card_layout.setSpacing(8)

        # CACHE Section
        card_layout.addWidget(_create_section_header("Cache"))

        self.spin_step = QtWidgets.QDoubleSpinBox(self)
        self.spin_step.setRange(0.01, 100.0)
        self.spin_step.setSingleStep(0.1)
        self.spin_step.setDecimals(2)
        self.spin_step.setValue(1.0)
        self.spin_step.setFixedWidth(80)
        self.spin_step.setToolTip("Sampling interval used during cache export.")
        card_layout.addLayout(_create_form_row("Frame Step", self.spin_step, parent=self))

        self.spin_handles = QtWidgets.QSpinBox(self)
        self.spin_handles.setRange(0, 100)
        self.spin_handles.setValue(0)
        self.spin_handles.setFixedWidth(80)
        self.spin_handles.setToolTip("Extra frames exported before and after the active range.")
        card_layout.addLayout(_create_form_row("Frame Handles", self.spin_handles, parent=self))

        card_layout.addSpacing(4)

        # GEOMETRY Section
        card_layout.addWidget(_create_section_header("Geometry"))

        self.chk_uvs = QtWidgets.QCheckBox("UVs", self)
        self.chk_uvs.setToolTip("Preserves UV texture coordinates in Alembic cache.")
        card_layout.addWidget(self.chk_uvs)

        self.chk_normals = QtWidgets.QCheckBox("Normals", self)
        self.chk_normals.setToolTip("Preserves vertex normals and shading data.")
        card_layout.addWidget(self.chk_normals)

        self.chk_visibility = QtWidgets.QCheckBox("Visibility", self)
        self.chk_visibility.setToolTip("Exports object visibility animation.")
        card_layout.addWidget(self.chk_visibility)

        self.chk_face_sets = QtWidgets.QCheckBox("Face Sets", self)
        self.chk_face_sets.setToolTip("Preserves Alembic face-set material assignments.")
        card_layout.addWidget(self.chk_face_sets)

        self.chk_color_sets = QtWidgets.QCheckBox("Color Sets", self)
        self.chk_color_sets.setToolTip("Exports vertex color streams.")
        card_layout.addWidget(self.chk_color_sets)

        card_layout.addSpacing(4)

        # TRANSFORM Section
        card_layout.addWidget(_create_section_header("Transform"))

        self.chk_world_space = QtWidgets.QCheckBox("World Space", self)
        self.chk_world_space.setToolTip("Exports transforms in world-space coordinates.")
        card_layout.addWidget(self.chk_world_space)

        root.addWidget(card)

        # Bottom Action Footer
        footer_layout = QtWidgets.QHBoxLayout()
        footer_layout.setContentsMargins(0, 8, 0, 0)

        self.btn_reset = create_button("Reset", role="secondary", fixed_width=75, parent=self)
        self.btn_reset.setToolTip("Reset Alembic settings to pipeline defaults")

        self.btn_cancel = create_button("Cancel", role="secondary", fixed_width=75, parent=self)
        self.btn_save = create_button("Save", role="primary", fixed_width=80, parent=self)

        footer_layout.addWidget(self.btn_reset)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.btn_cancel)
        footer_layout.addWidget(self.btn_save)
        root.addLayout(footer_layout)

        # Connect signals
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._on_save)

    def _load_values(self):
        cfg = get_anim_export_settings()["alembic"]
        self.spin_step.setValue(float(cfg.get("step", 1.0)))
        self.spin_handles.setValue(int(cfg.get("handles", 0)))
        self.chk_uvs.setChecked(bool(cfg.get("uvs", True)))
        self.chk_normals.setChecked(bool(cfg.get("normals", True)))
        self.chk_visibility.setChecked(bool(cfg.get("visibility", True)))
        self.chk_face_sets.setChecked(bool(cfg.get("face_sets", True)))
        self.chk_color_sets.setChecked(bool(cfg.get("color_sets", False)))
        self.chk_world_space.setChecked(bool(cfg.get("world_space", True)))

    def _on_reset(self):
        reset_anim_export_settings(scope="alembic")
        self._load_values()
        emit_log("Alembic settings reset to default.", level="INFO", source="Anim Export")

    def _on_save(self):
        step_val = self.spin_step.value()
        if step_val <= 0.0:
            emit_log("Invalid Alembic frame step: must be greater than 0.", level="WARNING", source="Anim Export")
            return

        handles_val = self.spin_handles.value()
        if handles_val < 0:
            emit_log("Invalid Alembic frame handles: must be 0 or positive.", level="WARNING", source="Anim Export")
            return

        alembic_data = {
            "step": float(step_val),
            "handles": int(handles_val),
            "uvs": bool(self.chk_uvs.isChecked()),
            "normals": bool(self.chk_normals.isChecked()),
            "visibility": bool(self.chk_visibility.isChecked()),
            "face_sets": bool(self.chk_face_sets.isChecked()),
            "color_sets": bool(self.chk_color_sets.isChecked()),
            "world_space": bool(self.chk_world_space.isChecked()),
        }

        save_anim_export_settings({"alembic": alembic_data})
        emit_log("Alembic settings saved.", level="INFO", source="Anim Export")
        self.accept()


# ==============================================================================
# 🎬 Dedicated Compact FBX Settings Dialog
# ==============================================================================

class FBXSettingsDialog(BaseToolDialog):
    """Compact FBX Animation Export Configuration Dialog."""

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
        configure_window(self, (380, 440), (440, 500))

        self._build_ui()
        self._load_values()
        apply_theme(self)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Header
        header, _ = create_brand_header(
            "FBX SETTINGS",
            "Animation export options",
            parent=self,
        )
        root.addWidget(header)

        # Main Card Panel
        card = QtWidgets.QFrame(self)
        card.setObjectName("ActionCard")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(14, 10, 14, 14)
        card_layout.setSpacing(8)

        # ANIMATION Section
        card_layout.addWidget(_create_section_header("Animation"))

        self.chk_bake = QtWidgets.QCheckBox("Bake Animation", self)
        self.chk_bake.setToolTip("Bakes simulation and animation constraints into keyframes.")
        card_layout.addWidget(self.chk_bake)

        self.spin_step = QtWidgets.QSpinBox(self)
        self.spin_step.setRange(1, 100)
        self.spin_step.setValue(1)
        self.spin_step.setFixedWidth(80)
        self.spin_step.setToolTip("Frame step interval for animation baking.")
        card_layout.addLayout(_create_form_row("Step", self.spin_step, parent=self))

        self.chk_resample = QtWidgets.QCheckBox("Resample Animation", self)
        self.chk_resample.setToolTip("Resamples dense animation curves to baked keys.")
        card_layout.addWidget(self.chk_resample)

        self.chk_euler = QtWidgets.QCheckBox("Euler Filter", self)
        self.chk_euler.setToolTip("Filters rotational discontinuities after baking.")
        card_layout.addWidget(self.chk_euler)

        card_layout.addSpacing(4)

        # DEFORMATION Section
        card_layout.addWidget(_create_section_header("Deformation"))

        self.chk_skin = QtWidgets.QCheckBox("Skin", self)
        self.chk_skin.setToolTip("Exports skinCluster skeletal deformation.")
        card_layout.addWidget(self.chk_skin)

        self.chk_blend_shapes = QtWidgets.QCheckBox("Blend Shapes", self)
        self.chk_blend_shapes.setToolTip("Includes blend shape deformation data in FBX export.")
        card_layout.addWidget(self.chk_blend_shapes)

        card_layout.addSpacing(4)

        # GEOMETRY Section
        card_layout.addWidget(_create_section_header("Geometry"))

        self.chk_smoothing = QtWidgets.QCheckBox("Smoothing Groups", self)
        self.chk_smoothing.setToolTip("Preserves polygon edge smoothing groups.")
        card_layout.addWidget(self.chk_smoothing)

        card_layout.addSpacing(4)

        # SCENE Section
        card_layout.addWidget(_create_section_header("Scene"))

        self.chk_cameras = QtWidgets.QCheckBox("Cameras", self)
        self.chk_cameras.setToolTip("Exports shot camera animation and camera attributes.")
        card_layout.addWidget(self.chk_cameras)

        root.addWidget(card)

        # Bottom Action Footer
        footer_layout = QtWidgets.QHBoxLayout()
        footer_layout.setContentsMargins(0, 8, 0, 0)

        self.btn_reset = create_button("Reset", role="secondary", fixed_width=75, parent=self)
        self.btn_reset.setToolTip("Reset FBX settings to pipeline defaults")

        self.btn_cancel = create_button("Cancel", role="secondary", fixed_width=75, parent=self)
        self.btn_save = create_button("Save", role="primary", fixed_width=80, parent=self)

        footer_layout.addWidget(self.btn_reset)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.btn_cancel)
        footer_layout.addWidget(self.btn_save)
        root.addLayout(footer_layout)

        # Connect signals
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._on_save)

    def _load_values(self):
        cfg = get_anim_export_settings()["fbx"]
        self.chk_bake.setChecked(bool(cfg.get("bake_animation", True)))
        self.spin_step.setValue(int(cfg.get("step", 1)))
        self.chk_resample.setChecked(bool(cfg.get("resample", True)))
        self.chk_euler.setChecked(bool(cfg.get("euler_filter", False)))
        self.chk_skin.setChecked(bool(cfg.get("skin", True)))
        self.chk_blend_shapes.setChecked(bool(cfg.get("blend_shapes", True)))
        self.chk_smoothing.setChecked(bool(cfg.get("smoothing_groups", True)))
        self.chk_cameras.setChecked(bool(cfg.get("cameras", True)))

    def _on_reset(self):
        reset_anim_export_settings(scope="fbx")
        self._load_values()
        emit_log("FBX settings reset to default.", level="INFO", source="Anim Export")

    def _on_save(self):
        step_val = self.spin_step.value()
        if step_val < 1:
            emit_log("Invalid FBX step: must be 1 or greater.", level="WARNING", source="Anim Export")
            return

        fbx_data = {
            "bake_animation": bool(self.chk_bake.isChecked()),
            "step": int(step_val),
            "resample": bool(self.chk_resample.isChecked()),
            "euler_filter": bool(self.chk_euler.isChecked()),
            "skin": bool(self.chk_skin.isChecked()),
            "blend_shapes": bool(self.chk_blend_shapes.isChecked()),
            "smoothing_groups": bool(self.chk_smoothing.isChecked()),
            "cameras": bool(self.chk_cameras.isChecked()),
        }

        save_anim_export_settings({"fbx": fbx_data})
        emit_log("FBX settings saved.", level="INFO", source="Anim Export")
        self.accept()


# ==============================================================================
# Singleton Modal Launchers
# ==============================================================================

_ALEMBIC_DIALOG = None
_FBX_DIALOG = None


def show_alembic_settings(parent=None):
    """Open the dedicated Alembic settings dialog as a singleton."""
    global _ALEMBIC_DIALOG
    if _ALEMBIC_DIALOG is not None:
        try:
            _ALEMBIC_DIALOG.close()
            _ALEMBIC_DIALOG.deleteLater()
        except Exception:
            pass
    _ALEMBIC_DIALOG = AlembicSettingsDialog(parent=parent)
    register_window("scartools_anim_io_alembic_settings", _ALEMBIC_DIALOG)
    _ALEMBIC_DIALOG.show()
    return _ALEMBIC_DIALOG


def show_fbx_settings(parent=None):
    """Open the dedicated FBX settings dialog as a singleton."""
    global _FBX_DIALOG
    if _FBX_DIALOG is not None:
        try:
            _FBX_DIALOG.close()
            _FBX_DIALOG.deleteLater()
        except Exception:
            pass
    _FBX_DIALOG = FBXSettingsDialog(parent=parent)
    register_window("scartools_anim_io_fbx_settings", _FBX_DIALOG)
    _FBX_DIALOG.show()
    return _FBX_DIALOG
