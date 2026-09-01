# -*- coding: utf-8 -*-
"""
Dedicated Technical Settings Dialogs for Anim Export (Alembic & FBX Parameters).
Engineered with studio-grade spacing rhythm, vertical checkbox scanning,
clear child-dependent control hierarchy, and unified token alignment.
"""

from __future__ import absolute_import, division, print_function

import os
import re

from scartools import settings
from scartools.ui.qt import QtCore, QtWidgets, QtGui, maya_main_window
from scartools.ui.window import BaseToolDialog, register_window
from scartools.ui import (
    configure_window,
    configure_root_layout,
    configure_field,
    create_brand_header,
    create_button,
    create_section_panel,
    create_subheading,
    apply_theme,
    repolish,
    FORM_LABEL_WIDTH,
    FORM_ACTION_WIDTH,
    INLINE_SPACING,
    CHECKBOX_ROW_GAP,
    DEPENDENT_CONTROL_INDENT,
    SECTION_HEADING_TOP_GAP,
    SECTION_HEADING_BOTTOM_GAP,
)
from scartools.framework.logging import emit_log
from scartools.framework.paths import is_valid_filename as _is_valid_filename


# ==============================================================================
# Central Default Settings (Single Source of Truth)
# ==============================================================================

DEFAULT_ALEMBIC_SETTINGS = {
    # Sampling
    "start_frame": None,
    "end_frame": None,
    "step": 1.0,

    # Geometry
    "uvs": True,
    "all_uv_sets": True,
    "normals": True,
    "visibility": True,
    "face_sets": True,
    "color_sets": False,
    "auto_subd": False,
    "renderable_only": False,

    # Transform
    "world_space": True,
    "euler_filter": False,

    # Attributes
    "user_attributes": False,
    "attribute_prefix": "ABC_",

    # Naming
    "strip_namespaces": True,

    # File
    "data_format": "Ogawa",
    "output_path": "",
    "file_name": "",
}

DEFAULT_FBX_SETTINGS = {
    # Animation
    "bake_animation": True,
    "start_frame": None,
    "end_frame": None,
    "step": 1,
    "resample": True,
    "euler_filter": False,
    "constant_key_reducer": False,
    "quaternion_mode": "Resample",

    # Deformation
    "skin": True,
    "blend_shapes": True,

    # Geometry
    "smoothing_groups": True,
    "tangents_binormals": True,
    "smooth_mesh": False,
    "triangulate": False,

    # Scene
    "cameras": True,
    "lights": False,
    "constraints": False,
    "input_connections": False,
    "preserve_instances": False,

    # Coordinate System
    "units": "Centimeters",
    "up_axis": "Y",

    # File
    "file_type": "Binary",
    "fbx_version": "FBX 2020",
    "embed_media": False,
    "output_path": "",
    "file_name": "",

    # Naming
    "strip_namespaces": True,
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
    """Persist settings dictionary into central optionVar store."""
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
    dialog.setFixedWidth(420)
    apply_theme(dialog)

    root = QtWidgets.QVBoxLayout(dialog)
    root.setContentsMargins(20, 20, 20, 20)
    root.setSpacing(14)

    title_lbl = QtWidgets.QLabel("Reset Anim Export Settings?")
    title_lbl.setObjectName("DialogTitle")
    root.addWidget(title_lbl)

    msg_lbl = QtWidgets.QLabel(
        "This restores the ScarTools pipeline defaults for both FBX and Alembic shot export.\n\nAre you sure you want to proceed?"
    )
    msg_lbl.setWordWrap(True)
    msg_lbl.setObjectName("Muted")
    root.addWidget(msg_lbl)

    btn_row = QtWidgets.QHBoxLayout()
    btn_row.setSpacing(10)
    btn_row.addStretch(1)
    cancel_btn = create_button("Cancel", role="secondary", fixed_width=90, parent=dialog)
    reset_btn = create_button("Reset to Defaults", role="primary", fixed_width=155, parent=dialog)

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


_create_subheading = create_subheading


def _create_label(text, width=80):
    """Create a consistently aligned form label."""
    lbl = QtWidgets.QLabel(str(text))
    lbl.setFixedWidth(width)
    lbl.setObjectName("FieldLabel")
    return lbl


def _is_valid_filename(filename):
    """Check if filename contains no illegal Windows/POSIX characters. Empty string is allowed (uses default asset name)."""
    if not filename or not str(filename).strip():
        return True
    illegal_chars = r'[\\/:*?"<>|]'
    return not bool(re.search(illegal_chars, str(filename).strip()))


# ==============================================================================
# 🎬 Dedicated Technical Alembic Settings Dialog
# ==============================================================================

class AlembicSettingsDialog(BaseToolDialog):
    """Complete Technical Alembic Configuration with Refined Rhythm."""

    OBJECT_NAME = "ScarToolsAlembicSettingsDialog"
    TOOL_ID = "scartools_anim_io_alembic_settings"
    WINDOW_TITLE = "Alembic Settings"

    def __init__(self, parent=None, shot_context=None):
        super(AlembicSettingsDialog, self).__init__(
            parent=parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        configure_window(self, (460, 620), (520, 700))

        self.shot_context = shot_context or {}
        self._build_ui()
        self._load_values()
        apply_theme(self)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Brand Header
        header, _ = create_brand_header(
            "ALEMBIC SETTINGS",
            "Geometry cache export configuration",
            parent=self,
        )
        root.addWidget(header)

        # 2. Scrollable Body
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(0)

        # === SINGLE UNIFIED CARD ===
        main_card, card_layout, _ = create_section_panel("Parameters", accent="cache", layout_kind="vertical", parent=self)
        card_layout.setContentsMargins(14, 10, 14, 14)
        card_layout.setSpacing(CHECKBOX_ROW_GAP)

        # --- 1. SAMPLING ---
        card_layout.addWidget(_create_subheading("Sampling", is_first=True))

        samp_row1 = QtWidgets.QHBoxLayout()
        samp_row1.setSpacing(8)
        self.spin_start = QtWidgets.QSpinBox(self)
        self.spin_start.setRange(-999999, 999999)
        self.spin_start.setFixedWidth(90)
        configure_field(self.spin_start)
        self.spin_start.setToolTip("Start frame for Alembic cache extraction.")

        self.spin_end = QtWidgets.QSpinBox(self)
        self.spin_end.setRange(-999999, 999999)
        self.spin_end.setFixedWidth(90)
        configure_field(self.spin_end)
        self.spin_end.setToolTip("End frame for Alembic cache extraction.")

        samp_row1.addWidget(_create_label("Start Frame", 80))
        samp_row1.addWidget(self.spin_start)
        samp_row1.addSpacing(20)
        samp_row1.addWidget(_create_label("End Frame", 70))
        samp_row1.addWidget(self.spin_end)
        samp_row1.addStretch(1)
        card_layout.addLayout(samp_row1)

        samp_row2 = QtWidgets.QHBoxLayout()
        samp_row2.setSpacing(8)
        self.spin_step = QtWidgets.QDoubleSpinBox(self)
        self.spin_step.setRange(0.01, 100.0)
        self.spin_step.setSingleStep(0.1)
        self.spin_step.setDecimals(2)
        self.spin_step.setFixedWidth(90)
        configure_field(self.spin_step)
        self.spin_step.setToolTip("Sampling interval used during cache export.")

        samp_row2.addWidget(_create_label("Frame Step", 80))
        samp_row2.addWidget(self.spin_step)
        samp_row2.addStretch(1)
        card_layout.addLayout(samp_row2)

        # --- 2. GEOMETRY (Vertical Stack with Controlled Gap) ---
        card_layout.addWidget(_create_subheading("Geometry"))

        self.chk_uvs = QtWidgets.QCheckBox("UVs", self)
        self.chk_uvs.setToolTip("Export primary UV data.")
        card_layout.addWidget(self.chk_uvs)

        self.chk_all_uv_sets = QtWidgets.QCheckBox("All UV Sets", self)
        self.chk_all_uv_sets.setToolTip("Export all applicable Maya UV sets.")
        card_layout.addWidget(self.chk_all_uv_sets)

        self.chk_normals = QtWidgets.QCheckBox("Normals", self)
        self.chk_normals.setToolTip("Preserve source mesh normals/shading information.")
        card_layout.addWidget(self.chk_normals)

        self.chk_visibility = QtWidgets.QCheckBox("Visibility", self)
        self.chk_visibility.setToolTip("Preserve animated object visibility.")
        card_layout.addWidget(self.chk_visibility)

        self.chk_face_sets = QtWidgets.QCheckBox("Face Sets", self)
        self.chk_face_sets.setToolTip("Preserve Alembic face-set information useful for downstream assignments/grouping.")
        card_layout.addWidget(self.chk_face_sets)

        self.chk_color_sets = QtWidgets.QCheckBox("Color Sets", self)
        self.chk_color_sets.setToolTip("Export Maya vertex color/color-set data.")
        card_layout.addWidget(self.chk_color_sets)

        self.chk_auto_subd = QtWidgets.QCheckBox("Auto SubD", self)
        self.chk_auto_subd.setToolTip("Support SubD-related Alembic output and preserve crease/subdivision information where applicable.")
        card_layout.addWidget(self.chk_auto_subd)

        self.chk_renderable = QtWidgets.QCheckBox("Renderable Only", self)
        self.chk_renderable.setToolTip("Restrict export to renderable scene content when explicitly requested.")
        card_layout.addWidget(self.chk_renderable)

        # --- 3. TRANSFORM (Vertical Stack) ---
        card_layout.addWidget(_create_subheading("Transform"))

        self.chk_world_space = QtWidgets.QCheckBox("World Space", self)
        self.chk_world_space.setToolTip("Export final animated geometry/transforms in world-space coordinates.")
        card_layout.addWidget(self.chk_world_space)

        self.chk_euler = QtWidgets.QCheckBox("Euler Filter", self)
        self.chk_euler.setToolTip("Apply Euler filtering where transform rotations require it.")
        card_layout.addWidget(self.chk_euler)

        # --- 4. ATTRIBUTES (Dependent Control Hierarchy) ---
        card_layout.addWidget(_create_subheading("Attributes"))

        self.chk_user_attrs = QtWidgets.QCheckBox("User Attributes", self)
        self.chk_user_attrs.setToolTip("Allow export of custom Maya attributes.")
        card_layout.addWidget(self.chk_user_attrs)

        # Indented dependent child container
        attr_dep_widget = QtWidgets.QWidget(self)
        attr_dep_layout = QtWidgets.QHBoxLayout(attr_dep_widget)
        attr_dep_layout.setContentsMargins(DEPENDENT_CONTROL_INDENT, 2, 0, 2)
        attr_dep_layout.setSpacing(8)

        self.lbl_attr_prefix = _create_label("Attribute Prefix", 90)
        self.edit_attr_prefix = QtWidgets.QLineEdit("ABC_", self)
        self.edit_attr_prefix.setFixedWidth(140)
        configure_field(self.edit_attr_prefix)
        self.edit_attr_prefix.setToolTip("Attribute name prefix filter for exported user attributes.")

        attr_dep_layout.addWidget(self.lbl_attr_prefix)
        attr_dep_layout.addWidget(self.edit_attr_prefix)
        attr_dep_layout.addStretch(1)
        card_layout.addWidget(attr_dep_widget)

        self.chk_user_attrs.toggled.connect(self._on_user_attrs_toggled)

        # --- 5. NAMING ---
        card_layout.addWidget(_create_subheading("Naming"))

        self.chk_strip_namespaces = QtWidgets.QCheckBox("Strip Namespace", self)
        self.chk_strip_namespaces.setToolTip("Allow removal of Maya namespaces from exported Alembic hierarchy/names.")
        card_layout.addWidget(self.chk_strip_namespaces)

        # --- 6. FILE & DESTINATION ---
        card_layout.addWidget(_create_subheading("File & Destination"))

        df_row = QtWidgets.QHBoxLayout()
        df_row.setSpacing(8)
        self.combo_data_format = QtWidgets.QComboBox(self)
        self.combo_data_format.addItems(["Ogawa", "HDF5"])
        self.combo_data_format.setFixedWidth(140)
        configure_field(self.combo_data_format)
        self.combo_data_format.setToolTip("Underlying binary storage format for Alembic.")
        df_row.addWidget(_create_label("Data Format", 80))
        df_row.addWidget(self.combo_data_format)
        df_row.addStretch(1)
        card_layout.addLayout(df_row)

        path_row = QtWidgets.QHBoxLayout()
        path_row.setSpacing(8)
        self.edit_output_path = QtWidgets.QLineEdit(self)
        configure_field(self.edit_output_path)
        self.edit_output_path.setToolTip("Destination directory for exported Alembic cache files.")
        self.btn_browse_path = create_button("Browse", role="secondary", fixed_width=FORM_ACTION_WIDTH, parent=self)
        self.btn_browse_path.clicked.connect(self._on_browse_output_path)
        path_row.addWidget(_create_label("Output Path", 80))
        path_row.addWidget(self.edit_output_path, 1)
        path_row.addWidget(self.btn_browse_path)
        card_layout.addLayout(path_row)

        fn_row = QtWidgets.QHBoxLayout()
        fn_row.setSpacing(8)
        self.edit_file_name = QtWidgets.QLineEdit(self)
        configure_field(self.edit_file_name)
        self.edit_file_name.setToolTip("Base file name template for exported shot Alembic package.")
        fn_row.addWidget(_create_label("File Name", 80))
        fn_row.addWidget(self.edit_file_name, 1)
        spacer_w = QtWidgets.QWidget(self)
        spacer_w.setFixedWidth(FORM_ACTION_WIDTH)
        fn_row.addWidget(spacer_w)
        card_layout.addLayout(fn_row)

        scroll_layout.addWidget(main_card)
        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_content)
        root.addWidget(scroll, 1)

        # 3. Action Footer Frame
        footer_frame = QtWidgets.QFrame(self)
        footer_frame.setObjectName("ActionFooter")
        footer_frame.setFixedHeight(46)
        footer_layout = QtWidgets.QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(10, 5, 10, 5)
        footer_layout.setSpacing(8)

        self.btn_reset = create_button("Reset to Default", role="secondary", fixed_width=130, parent=self)
        self.btn_reset.setToolTip("Reset Alembic configuration to recommended pipeline defaults")

        self.btn_cancel = create_button("Cancel", role="secondary", fixed_width=80, parent=self)
        self.btn_save = create_button("Save", role="primary", fixed_width=95, parent=self)

        footer_layout.addWidget(self.btn_reset)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.btn_cancel)
        footer_layout.addWidget(self.btn_save)
        root.addWidget(footer_frame)

        # Signal connections
        self.chk_user_attrs.toggled.connect(self._on_user_attrs_toggled)
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._on_save)

    def _on_user_attrs_toggled(self, checked):
        """Update dependent controls state while preserving stored prefix string."""
        self.lbl_attr_prefix.setEnabled(checked)
        self.edit_attr_prefix.setEnabled(checked)

    def _on_bake_toggled(self, checked):
        """Dynamically enable or disable dependent bake controls."""
        self.chk_resample.setEnabled(checked)
        self.chk_key_reducer.setEnabled(checked)
        self.spin_step.setEnabled(checked)

    def _on_browse_output_path(self):
        cur = self.edit_output_path.text().strip() or os.getcwd()
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Alembic Output Directory", cur)
        if chosen:
            self.edit_output_path.setText(os.path.normpath(chosen).replace("\\", "/"))

    def _load_values(self):
        cfg = get_anim_export_settings()["alembic"]

        # Timeline defaults fallback
        ctx_start = self.shot_context.get("start_frame", 1001)
        ctx_end = self.shot_context.get("end_frame", 1064)
        ctx_root = self.shot_context.get("shot_root", "")
        ctx_name = self.shot_context.get("shot_name", "Asset_Name")

        start_val = cfg.get("start_frame") if cfg.get("start_frame") is not None else ctx_start
        end_val = cfg.get("end_frame") if cfg.get("end_frame") is not None else ctx_end

        self.spin_start.setValue(int(start_val))
        self.spin_end.setValue(int(end_val))
        self.spin_step.setValue(float(cfg.get("step", 1.0)))

        self.chk_uvs.setChecked(bool(cfg.get("uvs", True)))
        self.chk_all_uv_sets.setChecked(bool(cfg.get("all_uv_sets", True)))
        self.chk_normals.setChecked(bool(cfg.get("normals", True)))
        self.chk_visibility.setChecked(bool(cfg.get("visibility", True)))
        self.chk_face_sets.setChecked(bool(cfg.get("face_sets", True)))
        self.chk_color_sets.setChecked(bool(cfg.get("color_sets", False)))
        self.chk_auto_subd.setChecked(bool(cfg.get("auto_subd", False)))
        self.chk_renderable.setChecked(bool(cfg.get("renderable_only", False)))

        self.chk_world_space.setChecked(bool(cfg.get("world_space", True)))
        self.chk_euler.setChecked(bool(cfg.get("euler_filter", False)))

        user_attrs = bool(cfg.get("user_attributes", False))
        self.chk_user_attrs.setChecked(user_attrs)
        self.edit_attr_prefix.setText(str(cfg.get("attribute_prefix", "ABC_")))
        self._on_user_attrs_toggled(user_attrs)

        self.chk_strip_namespaces.setChecked(bool(cfg.get("strip_namespaces", True)))

        df = str(cfg.get("data_format", "Ogawa"))
        idx = self.combo_data_format.findText(df, QtCore.Qt.MatchFixedString)
        if idx >= 0:
            self.combo_data_format.setCurrentIndex(idx)

        out_path = cfg.get("output_path") or (os.path.join(ctx_root, "Alembic").replace("\\", "/") if ctx_root else "")
        self.edit_output_path.setText(out_path)

        f_name = cfg.get("file_name") or ctx_name
        self.edit_file_name.setText(f_name)

    def _on_reset(self):
        reset_anim_export_settings(scope="alembic")
        self._load_values()
        emit_log("Alembic settings restored to default.", level="INFO", source="Anim Export")

    def _on_save(self):
        step_val = self.spin_step.value()
        if step_val <= 0.0:
            emit_log("Invalid Alembic frame step: must be greater than 0.", level="WARNING", source="Anim Export")
            return

        start_val = self.spin_start.value()
        end_val = self.spin_end.value()
        if start_val > end_val:
            emit_log("Warning: Start frame is greater than End frame.", level="WARNING", source="Anim Export")

        fname = self.edit_file_name.text().strip()
        if not _is_valid_filename(fname):
            emit_log("Invalid Alembic file name: contains illegal characters.", level="WARNING", source="Anim Export")
            return

        alembic_data = {
            "start_frame": int(start_val),
            "end_frame": int(end_val),
            "step": float(step_val),
            "uvs": bool(self.chk_uvs.isChecked()),
            "all_uv_sets": bool(self.chk_all_uv_sets.isChecked()),
            "normals": bool(self.chk_normals.isChecked()),
            "visibility": bool(self.chk_visibility.isChecked()),
            "face_sets": bool(self.chk_face_sets.isChecked()),
            "color_sets": bool(self.chk_color_sets.isChecked()),
            "auto_subd": bool(self.chk_auto_subd.isChecked()),
            "renderable_only": bool(self.chk_renderable.isChecked()),
            "world_space": bool(self.chk_world_space.isChecked()),
            "euler_filter": bool(self.chk_euler.isChecked()),
            "user_attributes": bool(self.chk_user_attrs.isChecked()),
            "attribute_prefix": str(self.edit_attr_prefix.text().strip()),
            "strip_namespaces": bool(self.chk_strip_namespaces.isChecked()),
            "data_format": str(self.combo_data_format.currentText()),
            "output_path": str(self.edit_output_path.text().strip()),
            "file_name": fname,
        }

        save_anim_export_settings({"alembic": alembic_data})
        emit_log("Alembic settings saved.", level="INFO", source="Anim Export")
        self.accept()


# ==============================================================================
# 🎬 Dedicated Technical FBX Settings Dialog
# ==============================================================================

class FBXSettingsDialog(BaseToolDialog):
    """Complete Technical FBX Configuration with Refined Rhythm."""

    OBJECT_NAME = "ScarToolsFBXSettingsDialog"
    TOOL_ID = "scartools_anim_io_fbx_settings"
    WINDOW_TITLE = "FBX Settings"

    def __init__(self, parent=None, shot_context=None):
        super(FBXSettingsDialog, self).__init__(
            parent=parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        configure_window(self, (460, 640), (520, 720))

        self.shot_context = shot_context or {}
        self._build_ui()
        self._load_values()
        apply_theme(self)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Brand Header
        header, _ = create_brand_header(
            "FBX SETTINGS",
            "Animation export configuration",
            parent=self,
        )
        root.addWidget(header)

        # 2. Scrollable Body
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(0)

        # === SINGLE UNIFIED CARD ===
        main_card, card_layout, _ = create_section_panel("Parameters", accent="cache", layout_kind="vertical", parent=self)
        card_layout.setContentsMargins(14, 10, 14, 14)
        card_layout.setSpacing(CHECKBOX_ROW_GAP)

        # --- 1. ANIMATION ---
        card_layout.addWidget(_create_subheading("Animation", is_first=True))

        anim_row1 = QtWidgets.QHBoxLayout()
        anim_row1.setSpacing(8)
        self.spin_start = QtWidgets.QSpinBox(self)
        self.spin_start.setRange(-999999, 999999)
        self.spin_start.setFixedWidth(90)
        configure_field(self.spin_start)

        self.spin_end = QtWidgets.QSpinBox(self)
        self.spin_end.setRange(-999999, 999999)
        self.spin_end.setFixedWidth(90)
        configure_field(self.spin_end)

        anim_row1.addWidget(_create_label("Start Frame", 80))
        anim_row1.addWidget(self.spin_start)
        anim_row1.addSpacing(20)
        anim_row1.addWidget(_create_label("End Frame", 70))
        anim_row1.addWidget(self.spin_end)
        anim_row1.addStretch(1)
        card_layout.addLayout(anim_row1)

        anim_row2 = QtWidgets.QHBoxLayout()
        anim_row2.setSpacing(8)
        self.spin_step = QtWidgets.QSpinBox(self)
        self.spin_step.setRange(1, 100)
        self.spin_step.setFixedWidth(90)
        configure_field(self.spin_step)

        self.combo_quaternion = QtWidgets.QComboBox(self)
        self.combo_quaternion.addItems(["Resample", "Euler", "Keep"])
        self.combo_quaternion.setFixedWidth(115)
        configure_field(self.combo_quaternion)

        anim_row2.addWidget(_create_label("Step", 80))
        anim_row2.addWidget(self.spin_step)
        anim_row2.addSpacing(20)
        anim_row2.addWidget(_create_label("Quaternion", 70))
        anim_row2.addWidget(self.combo_quaternion)
        anim_row2.addStretch(1)
        card_layout.addLayout(anim_row2)

        self.chk_bake = QtWidgets.QCheckBox("Bake Animation", self)
        self.chk_bake.setToolTip("Bake evaluated rig/constraint/controller animation into exportable animation.")
        card_layout.addWidget(self.chk_bake)

        self.chk_resample = QtWidgets.QCheckBox("Resample Animation", self)
        self.chk_euler = QtWidgets.QCheckBox("Euler Filter", self)
        self.chk_key_reducer = QtWidgets.QCheckBox("Constant Key Reducer", self)

        card_layout.addWidget(self.chk_resample)
        card_layout.addWidget(self.chk_euler)
        card_layout.addWidget(self.chk_key_reducer)

        # --- 2. DEFORMATION (Vertical Stack) ---
        card_layout.addWidget(_create_subheading("Deformation"))

        self.chk_skin = QtWidgets.QCheckBox("Skin", self)
        self.chk_blend_shapes = QtWidgets.QCheckBox("Blend Shapes", self)

        card_layout.addWidget(self.chk_skin)
        card_layout.addWidget(self.chk_blend_shapes)

        # --- 3. GEOMETRY (Vertical Stack) ---
        card_layout.addWidget(_create_subheading("Geometry"))

        self.chk_smoothing = QtWidgets.QCheckBox("Smoothing Groups", self)
        self.chk_tangents = QtWidgets.QCheckBox("Tangents & Binormals", self)
        self.chk_smooth_mesh = QtWidgets.QCheckBox("Smooth Mesh", self)
        self.chk_triangulate = QtWidgets.QCheckBox("Triangulate", self)

        card_layout.addWidget(self.chk_smoothing)
        card_layout.addWidget(self.chk_tangents)
        card_layout.addWidget(self.chk_smooth_mesh)
        card_layout.addWidget(self.chk_triangulate)

        # --- 4. SCENE (Vertical Stack) ---
        card_layout.addWidget(_create_subheading("Scene"))

        self.chk_cameras = QtWidgets.QCheckBox("Cameras", self)
        self.chk_lights = QtWidgets.QCheckBox("Lights", self)
        self.chk_constraints = QtWidgets.QCheckBox("Constraints", self)
        self.chk_inputs = QtWidgets.QCheckBox("Input Connections", self)
        self.chk_instances = QtWidgets.QCheckBox("Preserve Instances", self)

        card_layout.addWidget(self.chk_cameras)
        card_layout.addWidget(self.chk_lights)
        card_layout.addWidget(self.chk_constraints)
        card_layout.addWidget(self.chk_inputs)
        card_layout.addWidget(self.chk_instances)

        # --- 5. COORDINATE SYSTEM ---
        card_layout.addWidget(_create_subheading("Coordinate System"))

        coord_row = QtWidgets.QHBoxLayout()
        coord_row.setSpacing(8)
        self.combo_units = QtWidgets.QComboBox(self)
        self.combo_units.addItems(["Centimeters", "Meters", "Millimeters", "Inches", "Feet"])
        self.combo_units.setFixedWidth(120)
        configure_field(self.combo_units)

        self.combo_up_axis = QtWidgets.QComboBox(self)
        self.combo_up_axis.addItems(["Y", "Z"])
        self.combo_up_axis.setFixedWidth(75)
        configure_field(self.combo_up_axis)

        coord_row.addWidget(_create_label("Units", 80))
        coord_row.addWidget(self.combo_units)
        coord_row.addSpacing(20)
        coord_row.addWidget(_create_label("Up Axis", 55))
        coord_row.addWidget(self.combo_up_axis)
        coord_row.addStretch(1)
        card_layout.addLayout(coord_row)

        # --- 6. FILE ---
        card_layout.addWidget(_create_subheading("File"))

        ver_row = QtWidgets.QHBoxLayout()
        ver_row.setSpacing(8)
        self.combo_file_type = QtWidgets.QComboBox(self)
        self.combo_file_type.addItems(["Binary", "ASCII"])
        self.combo_file_type.setFixedWidth(120)
        configure_field(self.combo_file_type)

        self.combo_fbx_version = QtWidgets.QComboBox(self)
        self.combo_fbx_version.addItems(["FBX 2020", "FBX 2019", "FBX 2018", "FBX 2016/2017", "FBX 2014/2015"])
        self.combo_fbx_version.setFixedWidth(120)
        configure_field(self.combo_fbx_version)

        ver_row.addWidget(_create_label("File Type", 80))
        ver_row.addWidget(self.combo_file_type)
        ver_row.addSpacing(20)
        ver_row.addWidget(_create_label("Version", 55))
        ver_row.addWidget(self.combo_fbx_version)
        ver_row.addStretch(1)
        card_layout.addLayout(ver_row)

        self.chk_embed_media = QtWidgets.QCheckBox("Embed Media", self)
        card_layout.addWidget(self.chk_embed_media)

        path_row = QtWidgets.QHBoxLayout()
        path_row.setSpacing(8)
        self.edit_output_path = QtWidgets.QLineEdit(self)
        configure_field(self.edit_output_path)
        self.btn_browse_path = create_button("Browse", role="secondary", fixed_width=FORM_ACTION_WIDTH, parent=self)
        self.btn_browse_path.clicked.connect(self._on_browse_output_path)
        path_row.addWidget(_create_label("Output Path", 80))
        path_row.addWidget(self.edit_output_path, 1)
        path_row.addWidget(self.btn_browse_path)
        card_layout.addLayout(path_row)

        fn_row = QtWidgets.QHBoxLayout()
        fn_row.setSpacing(8)
        self.edit_file_name = QtWidgets.QLineEdit(self)
        configure_field(self.edit_file_name)
        fn_row.addWidget(_create_label("File Name", 80))
        fn_row.addWidget(self.edit_file_name, 1)
        spacer_w = QtWidgets.QWidget(self)
        spacer_w.setFixedWidth(FORM_ACTION_WIDTH)
        fn_row.addWidget(spacer_w)
        card_layout.addLayout(fn_row)

        # --- 7. NAMING ---
        card_layout.addWidget(_create_subheading("Naming"))

        self.chk_strip_namespaces = QtWidgets.QCheckBox("Strip Namespace", self)
        card_layout.addWidget(self.chk_strip_namespaces)

        scroll_layout.addWidget(main_card)
        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_content)
        root.addWidget(scroll, 1)

        # 3. Action Footer Container
        footer_frame = QtWidgets.QFrame(self)
        footer_frame.setObjectName("ActionFooter")
        footer_frame.setFixedHeight(46)
        footer_layout = QtWidgets.QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(10, 5, 10, 5)
        footer_layout.setSpacing(8)

        self.btn_reset = create_button("Reset to Default", role="secondary", fixed_width=130, parent=self)
        self.btn_reset.setToolTip("Reset FBX configuration to recommended pipeline defaults")

        self.btn_cancel = create_button("Cancel", role="secondary", fixed_width=80, parent=self)
        self.btn_save = create_button("Save", role="primary", fixed_width=95, parent=self)

        footer_layout.addWidget(self.btn_reset)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.btn_cancel)
        footer_layout.addWidget(self.btn_save)
        root.addWidget(footer_frame)

        # Signal connections
        self.chk_bake.toggled.connect(self._on_bake_toggled)
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._on_save)

    def _on_bake_toggled(self, checked):
        """Dynamically enable or disable dependent bake controls."""
        self.chk_resample.setEnabled(checked)
        self.chk_key_reducer.setEnabled(checked)
        self.spin_step.setEnabled(checked)

    def _on_browse_output_path(self):
        cur = self.edit_output_path.text().strip() or os.getcwd()
        chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Select FBX Output Directory", cur)
        if chosen:
            self.edit_output_path.setText(os.path.normpath(chosen).replace("\\", "/"))

    def _load_values(self):
        cfg = get_anim_export_settings()["fbx"]

        # Timeline defaults fallback
        ctx_start = self.shot_context.get("start_frame", 1001)
        ctx_end = self.shot_context.get("end_frame", 1064)
        ctx_root = self.shot_context.get("shot_root", "")
        ctx_name = self.shot_context.get("shot_name", "Asset_Name")

        start_val = cfg.get("start_frame") if cfg.get("start_frame") is not None else ctx_start
        end_val = cfg.get("end_frame") if cfg.get("end_frame") is not None else ctx_end

        self.spin_start.setValue(int(start_val))
        self.spin_end.setValue(int(end_val))
        self.spin_step.setValue(int(cfg.get("step", 1)))
        self.chk_bake.setChecked(bool(cfg.get("bake_animation", True)))
        self.chk_resample.setChecked(bool(cfg.get("resample", True)))
        self.chk_euler.setChecked(bool(cfg.get("euler_filter", False)))
        self.chk_key_reducer.setChecked(bool(cfg.get("constant_key_reducer", False)))

        qm = str(cfg.get("quaternion_mode", "Resample"))
        idx_qm = self.combo_quaternion.findText(qm, QtCore.Qt.MatchFixedString)
        if idx_qm >= 0:
            self.combo_quaternion.setCurrentIndex(idx_qm)

        self.chk_skin.setChecked(bool(cfg.get("skin", True)))
        self.chk_blend_shapes.setChecked(bool(cfg.get("blend_shapes", True)))

        self.chk_smoothing.setChecked(bool(cfg.get("smoothing_groups", True)))
        self.chk_tangents.setChecked(bool(cfg.get("tangents_binormals", True)))
        self.chk_smooth_mesh.setChecked(bool(cfg.get("smooth_mesh", False)))
        self.chk_triangulate.setChecked(bool(cfg.get("triangulate", False)))

        self.chk_cameras.setChecked(bool(cfg.get("cameras", True)))
        self.chk_lights.setChecked(bool(cfg.get("lights", False)))
        self.chk_constraints.setChecked(bool(cfg.get("constraints", False)))
        self.chk_inputs.setChecked(bool(cfg.get("input_connections", False)))
        self.chk_instances.setChecked(bool(cfg.get("preserve_instances", False)))

        units_val = str(cfg.get("units", "Centimeters"))
        idx_u = self.combo_units.findText(units_val, QtCore.Qt.MatchFixedString)
        if idx_u >= 0:
            self.combo_units.setCurrentIndex(idx_u)

        up_val = str(cfg.get("up_axis", "Y"))
        idx_up = self.combo_up_axis.findText(up_val, QtCore.Qt.MatchFixedString)
        if idx_up >= 0:
            self.combo_up_axis.setCurrentIndex(idx_up)

        ft_val = str(cfg.get("file_type", "Binary"))
        idx_ft = self.combo_file_type.findText(ft_val, QtCore.Qt.MatchFixedString)
        if idx_ft >= 0:
            self.combo_file_type.setCurrentIndex(idx_ft)

        ver_val = str(cfg.get("fbx_version", "FBX 2020"))
        idx_ver = self.combo_fbx_version.findText(ver_val, QtCore.Qt.MatchFixedString)
        if idx_ver >= 0:
            self.combo_fbx_version.setCurrentIndex(idx_ver)

        self.chk_embed_media.setChecked(bool(cfg.get("embed_media", False)))

        out_path = cfg.get("output_path") or (os.path.join(ctx_root, "FBX").replace("\\", "/") if ctx_root else "")
        self.edit_output_path.setText(out_path)

        f_name = cfg.get("file_name") or ctx_name
        self.edit_file_name.setText(f_name)

        self.chk_strip_namespaces.setChecked(bool(cfg.get("strip_namespaces", True)))

    def _on_reset(self):
        reset_anim_export_settings(scope="fbx")
        self._load_values()
        emit_log("FBX settings restored to default.", level="INFO", source="Anim Export")

    def _on_save(self):
        step_val = self.spin_step.value()
        if step_val < 1:
            emit_log("Invalid FBX step: must be 1 or greater.", level="WARNING", source="Anim Export")
            return

        start_val = self.spin_start.value()
        end_val = self.spin_end.value()
        if start_val > end_val:
            emit_log("Warning: Start frame is greater than End frame.", level="WARNING", source="Anim Export")

        fname = self.edit_file_name.text().strip()
        if not _is_valid_filename(fname):
            emit_log("Invalid FBX file name: contains illegal characters.", level="WARNING", source="Anim Export")
            return

        fbx_data = {
            "bake_animation": bool(self.chk_bake.isChecked()),
            "start_frame": int(start_val),
            "end_frame": int(end_val),
            "step": int(step_val),
            "resample": bool(self.chk_resample.isChecked()),
            "euler_filter": bool(self.chk_euler.isChecked()),
            "constant_key_reducer": bool(self.chk_key_reducer.isChecked()),
            "quaternion_mode": str(self.combo_quaternion.currentText()),
            "skin": bool(self.chk_skin.isChecked()),
            "blend_shapes": bool(self.chk_blend_shapes.isChecked()),
            "smoothing_groups": bool(self.chk_smoothing.isChecked()),
            "tangents_binormals": bool(self.chk_tangents.isChecked()),
            "smooth_mesh": bool(self.chk_smooth_mesh.isChecked()),
            "triangulate": bool(self.chk_triangulate.isChecked()),
            "cameras": bool(self.chk_cameras.isChecked()),
            "lights": bool(self.chk_lights.isChecked()),
            "constraints": bool(self.chk_constraints.isChecked()),
            "input_connections": bool(self.chk_inputs.isChecked()),
            "preserve_instances": bool(self.chk_instances.isChecked()),
            "units": str(self.combo_units.currentText()),
            "up_axis": str(self.combo_up_axis.currentText()),
            "file_type": str(self.combo_file_type.currentText()),
            "fbx_version": str(self.combo_fbx_version.currentText()),
            "embed_media": bool(self.chk_embed_media.isChecked()),
            "output_path": str(self.edit_output_path.text().strip()),
            "file_name": fname,
            "strip_namespaces": bool(self.chk_strip_namespaces.isChecked()),
        }

        save_anim_export_settings({"fbx": fbx_data})
        emit_log("FBX settings saved.", level="INFO", source="Anim Export")
        self.accept()


# ==============================================================================
# Singleton Modal Launchers
# ==============================================================================

_ALEMBIC_DIALOG = None
_FBX_DIALOG = None


def show_alembic_settings(parent=None, shot_context=None):
    """Open the dedicated Alembic settings dialog as a singleton."""
    global _ALEMBIC_DIALOG
    if _ALEMBIC_DIALOG is not None:
        try:
            _ALEMBIC_DIALOG.close()
            _ALEMBIC_DIALOG.deleteLater()
        except Exception:
            pass
    _ALEMBIC_DIALOG = AlembicSettingsDialog(parent=parent, shot_context=shot_context)
    register_window("scartools_anim_io_alembic_settings", _ALEMBIC_DIALOG)
    _ALEMBIC_DIALOG.show()
    _ALEMBIC_DIALOG.raise_()
    _ALEMBIC_DIALOG.activateWindow()
    return _ALEMBIC_DIALOG


def show_fbx_settings(parent=None, shot_context=None):
    """Open the dedicated FBX settings dialog as a singleton."""
    global _FBX_DIALOG
    if _FBX_DIALOG is not None:
        try:
            _FBX_DIALOG.close()
            _FBX_DIALOG.deleteLater()
        except Exception:
            pass
    _FBX_DIALOG = FBXSettingsDialog(parent=parent, shot_context=shot_context)
    register_window("scartools_anim_io_fbx_settings", _FBX_DIALOG)
    _FBX_DIALOG.show()
    _FBX_DIALOG.raise_()
    _FBX_DIALOG.activateWindow()
    return _FBX_DIALOG


def close_settings_dialogs():
    """Cleanly close all open Alembic and FBX settings dialogs upon suite reload or license change."""
    global _ALEMBIC_DIALOG, _FBX_DIALOG
    if _ALEMBIC_DIALOG is not None:
        try:
            _ALEMBIC_DIALOG.close()
        except Exception:
            pass
        _ALEMBIC_DIALOG = None
    if _FBX_DIALOG is not None:
        try:
            _FBX_DIALOG.close()
        except Exception:
            pass
        _FBX_DIALOG = None
