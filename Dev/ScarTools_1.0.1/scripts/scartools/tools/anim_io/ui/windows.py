# -*- coding: utf-8 -*-
"""DCC Window for Animation Export & Import Suite."""

from __future__ import absolute_import, division, print_function

import os
import maya.cmds as cmds

from scartools.ui.qt import QtCore, QtWidgets, QtGui
from scartools.ui.window import BaseToolDialog, register_window
from scartools.ui.components import (
    create_brand_header,
    create_section_panel,
    create_action_footer,
    apply_theme,
)
from scartools.ui.controls import (
    create_segmented_control,
    create_toggle_switch,
)
from scartools.ui.widgets import (
    PathPickerWidget,
    create_path_picker,
)
from scartools.ui.theme import repolish
from scartools.ui import tokens

from ..controller import AnimIOController
from ..operations import discover_scene_assets, load_shot_manifest


class AnimIODialog(BaseToolDialog):
    """Main UI Dialog for ScarTools Animation Export & Import Suite."""

    TOOL_ID = "scartools_anim_io"
    WINDOW_TITLE = "ScarTools — Animation I/O Suite"

    def __init__(self, parent=None):
        super(AnimIODialog, self).__init__(parent=parent, tool_id=self.TOOL_ID)
        self.controller = AnimIOController()
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumWidth(460)
        self.resize(500, 680)

        self._build_ui()
        self.refresh_scene_data()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # 1. Brand Header
        header, _subtitle = create_brand_header(
            "ANIMATION I/O SUITE",
            "Shot Packaging, Alembic & FBX Cache Extraction & Assembly",
            parent=self,
        )
        root.addWidget(header)

        # 2. Mode Selector
        self.mode_control = create_segmented_control(
            ["📦 Export Shot", "📥 Import & Assemble"],
            current=0,
            parent=self,
        )
        self.mode_control.currentIndexChanged.connect(self._on_mode_changed)
        root.addWidget(self.mode_control)

        # 3. Stacked Content Area
        self.stack = QtWidgets.QStackedWidget(self)
        root.addWidget(self.stack, 1)

        # --- TAB 1: EXPORT PAGE ---
        export_widget = QtWidgets.QWidget(self)
        export_layout = QtWidgets.QVBoxLayout(export_widget)
        export_layout.setContentsMargins(0, 0, 0, 0)
        export_layout.setSpacing(8)

        # A. Target Destination Panel
        dest_panel, dest_layout, _ = create_section_panel("📁 TARGET DESTINATION & SHOT", accent="pipeline", parent=self)
        self.path_picker = PathPickerWidget(mode="directory", parent=self)
        dest_layout.addWidget(self.path_picker)

        shot_row = QtWidgets.QHBoxLayout()
        shot_lbl = QtWidgets.QLabel("Shot Name:", self)
        shot_lbl.setFixedWidth(75)
        self.shot_name_input = QtWidgets.QLineEdit(self)
        self.shot_name_input.setPlaceholderText("e.g. SQ01_SH010")
        self.shot_name_input.setText("SQ01_SH010")
        shot_row.addWidget(shot_lbl)
        shot_row.addWidget(self.shot_name_input)
        dest_layout.addLayout(shot_row)
        export_layout.addWidget(dest_panel)

        # B. Frame Range & Handles Panel
        range_panel, range_layout, _ = create_section_panel("⏱️ FRAME RANGE & HANDLES", accent="animation", parent=self)
        self.range_mode = create_segmented_control(["Timeline", "Custom"], current=0, parent=self)
        self.range_mode.currentIndexChanged.connect(self._on_range_mode_changed)
        range_layout.addWidget(self.range_mode)

        spin_row = QtWidgets.QHBoxLayout()
        start_f = 1001
        end_f = 1100
        try:
            if hasattr(cmds, "playbackOptions"):
                start_f = int(cmds.playbackOptions(q=True, minTime=True) or 1001)
                end_f = int(cmds.playbackOptions(q=True, maxTime=True) or 1100)
        except Exception:
            pass

        spin_row.addWidget(QtWidgets.QLabel("Start:", self))
        self.start_spin = QtWidgets.QSpinBox(self)
        self.start_spin.setRange(-999999, 999999)
        self.start_spin.setValue(start_f)
        spin_row.addWidget(self.start_spin)

        spin_row.addWidget(QtWidgets.QLabel("End:", self))
        self.end_spin = QtWidgets.QSpinBox(self)
        self.end_spin.setRange(-999999, 999999)
        self.end_spin.setValue(end_f)
        spin_row.addWidget(self.end_spin)

        spin_row.addWidget(QtWidgets.QLabel("Handles (±):", self))
        self.handles_spin = QtWidgets.QSpinBox(self)
        self.handles_spin.setRange(0, 100)
        self.handles_spin.setValue(5)
        spin_row.addWidget(self.handles_spin)
        range_layout.addLayout(spin_row)
        export_layout.addWidget(range_panel)

        # C. Camera Selection Panel
        cam_panel, cam_layout, _ = create_section_panel("🎥 SHOT CAMERA", accent="animation", parent=self)
        cam_row = QtWidgets.QHBoxLayout()
        cam_lbl = QtWidgets.QLabel("Camera:", self)
        cam_lbl.setFixedWidth(75)
        self.cam_combo = QtWidgets.QComboBox(self)
        self.cam_format_combo = QtWidgets.QComboBox(self)
        self.cam_format_combo.addItems(["FBX (.fbx)", "Alembic (.abc)"])
        self.cam_format_combo.setFixedWidth(110)
        cam_row.addWidget(cam_lbl)
        cam_row.addWidget(self.cam_combo, 1)
        cam_row.addWidget(self.cam_format_combo)
        cam_layout.addLayout(cam_row)
        export_layout.addWidget(cam_panel)

        # D. Characters & Props Panel
        asset_panel, asset_layout, _ = create_section_panel("🎭 CHARACTERS & PROPS", accent="animation", parent=self)
        fmt_row = QtWidgets.QHBoxLayout()
        fmt_lbl = QtWidgets.QLabel("Cache Format:", self)
        self.geo_format_combo = QtWidgets.QComboBox(self)
        self.geo_format_combo.addItems(["Alembic (.abc)", "FBX (.fbx)", "Both (.abc + .fbx)"])
        fmt_row.addWidget(fmt_lbl)
        fmt_row.addWidget(self.geo_format_combo, 1)
        asset_layout.addLayout(fmt_row)

        self.asset_list = QtWidgets.QListWidget(self)
        self.asset_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.asset_list.setMaximumHeight(140)
        asset_layout.addWidget(self.asset_list)

        btn_row = QtWidgets.QHBoxLayout()
        refresh_btn = QtWidgets.QPushButton("🔄 Refresh Scene", self)
        refresh_btn.clicked.connect(self.refresh_scene_data)
        select_all_btn = QtWidgets.QPushButton("Select All", self)
        select_all_btn.clicked.connect(self._select_all_assets)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(select_all_btn)
        asset_layout.addLayout(btn_row)

        # Velocity toggle
        vel_row = QtWidgets.QHBoxLayout()
        vel_lbl = QtWidgets.QLabel("Alembic Motion Blur Velocity Vectors", self)
        self.vel_toggle = create_toggle_switch(checked=True, parent=self)
        vel_row.addWidget(vel_lbl, 1)
        vel_row.addWidget(self.vel_toggle)
        asset_layout.addLayout(vel_row)
        export_layout.addWidget(asset_panel)

        self.stack.addWidget(export_widget)

        # --- TAB 2: IMPORT / ASSEMBLE PAGE ---
        import_widget = QtWidgets.QWidget(self)
        import_layout = QtWidgets.QVBoxLayout(import_widget)
        import_layout.setContentsMargins(0, 0, 0, 0)
        import_layout.setSpacing(10)

        in_panel, in_layout, _ = create_section_panel("📁 LOAD SHOT PACKAGE", accent="pipeline", parent=self)
        self.import_path_picker = PathPickerWidget(mode="directory", parent=self)
        self.import_path_picker.pathChanged.connect(self._on_import_path_changed)
        in_layout.addWidget(self.import_path_picker)
        import_layout.addWidget(in_panel)

        info_panel, info_layout, _ = create_section_panel("📋 SHOT MANIFEST DETAILS", accent="animation", parent=self)
        self.manifest_summary = QtWidgets.QTextEdit(self)
        self.manifest_summary.setReadOnly(True)
        self.manifest_summary.setPlaceholderText("Select a shot directory containing shot_manifest.json...")
        self.manifest_summary.setMaximumHeight(160)
        info_layout.addWidget(self.manifest_summary)
        import_layout.addWidget(info_panel)

        opts_panel, opts_layout, _ = create_section_panel("☑️ ASSEMBLY OPTIONS", accent="animation", parent=self)
        self.chk_time = QtWidgets.QCheckBox("Set Timeline Frame Range & FPS", self)
        self.chk_time.setChecked(True)
        self.chk_cam = QtWidgets.QCheckBox("Import Shot Camera (Lock Transforms)", self)
        self.chk_cam.setChecked(True)
        self.chk_chars = QtWidgets.QCheckBox("Import Character Geometry Caches", self)
        self.chk_chars.setChecked(True)
        self.chk_props = QtWidgets.QCheckBox("Import Prop Geometry Caches", self)
        self.chk_props.setChecked(True)
        opts_layout.addWidget(self.chk_time)
        opts_layout.addWidget(self.chk_cam)
        opts_layout.addWidget(self.chk_chars)
        opts_layout.addWidget(self.chk_props)
        import_layout.addWidget(opts_panel)
        import_layout.addStretch(1)

        self.stack.addWidget(import_widget)

        # 4. Action Footer
        (
            action_footer,
            self.message_label,
            self.apply_button,
            self.status_dot,
            self.status_label,
            self.view_log_button,
            _status_layout,
        ) = create_action_footer(
            "📦 EXPORT SHOT PACKAGE",
            message="Ready to package shot.",
            parent=self,
            include_log=False,
        )
        self.apply_button.clicked.connect(self._on_action_clicked)
        root.addWidget(action_footer)

        apply_theme(self)

    def _set_status(self, text, state="idle"):
        self.status_label.setText(str(text))
        self.status_label.setProperty("state", state)
        self.status_dot.setProperty("state", state)
        repolish(self.status_label)
        repolish(self.status_dot)

    def _set_message(self, text, state="neutral"):
        self.message_label.setText(str(text))
        self.message_label.setProperty("state", state)
        repolish(self.message_label)

    def _on_mode_changed(self, index):
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.apply_button.setText("📦 EXPORT SHOT PACKAGE")
            self._set_message("Ready to package shot.", "neutral")
            self._set_status("Ready", "idle")
        else:
            self.apply_button.setText("📥 ASSEMBLE SHOT SCENE")
            self._set_message("Select a shot package to assemble.", "neutral")
            self._set_status("Ready", "idle")

    def _on_range_mode_changed(self, index):
        if index == 0:  # Timeline
            try:
                if hasattr(cmds, "playbackOptions"):
                    self.start_spin.setValue(int(cmds.playbackOptions(q=True, minTime=True) or 1001))
                    self.end_spin.setValue(int(cmds.playbackOptions(q=True, maxTime=True) or 1100))
            except Exception:
                pass

    def refresh_scene_data(self):
        """Scan active Maya scene for cameras, characters, and props."""
        data = discover_scene_assets()

        # Cameras
        self.cam_combo.clear()
        cams = data.get("cameras", [])
        if cams:
            for c in cams:
                short = c.split("|")[-1]
                self.cam_combo.addItem(short, c)
        else:
            self.cam_combo.addItem("None (No custom camera)", None)

        # Characters & Props
        self.asset_list.clear()
        chars = data.get("characters", [])
        props = data.get("props", [])

        for c in chars:
            short = c.split("|")[-1]
            item = QtWidgets.QListWidgetItem("👤 [CHAR] " + short)
            item.setData(QtCore.Qt.UserRole, ("character", c))
            item.setCheckState(QtCore.Qt.Checked)
            self.asset_list.addItem(item)

        for p in props:
            short = p.split("|")[-1]
            item = QtWidgets.QListWidgetItem("📦 [PROP] " + short)
            item.setData(QtCore.Qt.UserRole, ("prop", p))
            item.setCheckState(QtCore.Qt.Checked)
            self.asset_list.addItem(item)

    def _select_all_assets(self):
        for i in range(self.asset_list.count()):
            self.asset_list.item(i).setCheckState(QtCore.Qt.Checked)

    def _on_import_path_changed(self, path):
        """Read manifest and populate summary."""
        manifest = load_shot_manifest(path)
        if not manifest:
            self.manifest_summary.setHtml("<span style='color:#E57373;'>⚠️ No valid shot_manifest.json found in this directory.</span>")
            self._set_message("No valid shot_manifest.json found.", "warning")
            self._set_status("No Manifest", "warning")
            return

        shot_name = manifest.get("shot_name", "Unknown")
        fps = manifest.get("fps", 24.0)
        fr = manifest.get("frame_range", {})
        cam = manifest.get("camera", {}).get("name", manifest.get("camera", {}).get("file", "None"))
        chars = len(manifest.get("characters", []))
        props = len(manifest.get("props", []))
        date = manifest.get("metadata", {}).get("timestamp", "")

        html = """
        <b>Shot:</b> {}<br>
        <b>Frame Range:</b> {} to {} (FPS: {})<br>
        <b>Camera:</b> {}<br>
        <b>Characters:</b> {} assets<br>
        <b>Props:</b> {} assets<br>
        <b>Export Date:</b> {}
        """.format(shot_name, fr.get("start"), fr.get("end"), fps, cam, chars, props, date)
        self.manifest_summary.setHtml(html)
        self._set_message("Manifest loaded for shot '{}'.".format(shot_name), "neutral")
        self._set_status("Manifest Loaded", "idle")

    def _on_action_clicked(self):
        mode = self.mode_control.current_index()
        if mode == 0:
            self._do_export()
        else:
            self._do_import()

    def _do_export(self):
        out_dir = self.path_picker.path()
        if not out_dir or not os.path.isdir(out_dir):
            self._set_message("Please specify a valid output directory.", "warning")
            self._set_status("Invalid Directory", "warning")
            return

        shot_name = self.shot_name_input.text().strip() or "untitled_shot"
        start_f = self.start_spin.value()
        end_f = self.end_spin.value()
        handles = self.handles_spin.value()

        # Camera
        cam_node = self.cam_combo.currentData()
        cam_fmt = "fbx" if self.cam_format_combo.currentIndex() == 0 else "abc"

        # Geo formats
        geo_idx = self.geo_format_combo.currentIndex()
        geo_fmts = ("abc",) if geo_idx == 0 else (("fbx",) if geo_idx == 1 else ("abc", "fbx"))

        # Selected assets
        chars = []
        props = []
        for i in range(self.asset_list.count()):
            item = self.asset_list.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                atype, anode = item.data(QtCore.Qt.UserRole)
                if atype == "character":
                    chars.append(anode)
                else:
                    props.append(anode)

        vel = self.vel_toggle.is_checked()

        try:
            self._set_message("Exporting shot package...", "neutral")
            self._set_status("Exporting...", "running")
            QtWidgets.QApplication.processEvents()

            from ..operations import export_shot_package
            res = export_shot_package(
                output_dir=out_dir,
                shot_name=shot_name,
                start_frame=start_f,
                end_frame=end_f,
                fps=24.0,
                camera_node=cam_node,
                camera_format=cam_fmt,
                character_nodes=chars,
                character_formats=geo_fmts,
                prop_nodes=props,
                prop_formats=geo_fmts,
                handles=handles,
                write_velocities=vel,
            )
            self._set_message("Exported shot '{}' successfully!".format(shot_name), "neutral")
            self._set_status("Export Success", "idle")
        except Exception as e:
            self._set_message("Export failed: {}".format(e), "warning")
            self._set_status("Export Failed", "error")

    def _do_import(self):
        in_path = self.import_path_picker.path()
        if not in_path:
            self._set_message("Please select a shot package folder.", "warning")
            self._set_status("No Folder Selected", "warning")
            return

        try:
            self._set_message("Assembling shot scene...", "neutral")
            self._set_status("Assembling...", "running")
            QtWidgets.QApplication.processEvents()

            from ..operations import import_shot_package
            res = import_shot_package(
                package_dir_or_manifest=in_path,
                import_time_settings=self.chk_time.isChecked(),
                import_camera=self.chk_cam.isChecked(),
                import_characters=self.chk_chars.isChecked(),
                import_props=self.chk_props.isChecked(),
                lock_camera=True,
            )
            self._set_message(
                "Assembled {} chars, {} props successfully!".format(
                    res.get("characters_imported", 0), res.get("props_imported", 0)
                ),
                "neutral",
            )
            self._set_status("Assembly Success", "idle")
        except Exception as e:
            self._set_message("Assembly failed: {}".format(e), "warning")
            self._set_status("Assembly Failed", "error")


_ACTIVE_DIALOG = None


def show_window():
    global _ACTIVE_DIALOG
    if _ACTIVE_DIALOG is not None:
        try:
            _ACTIVE_DIALOG.close()
            _ACTIVE_DIALOG.deleteLater()
        except Exception:
            pass
    _ACTIVE_DIALOG = AnimIODialog()
    register_window("scartools_anim_io", _ACTIVE_DIALOG)
    _ACTIVE_DIALOG.show()
    return _ACTIVE_DIALOG


def close_all_windows():
    global _ACTIVE_DIALOG
    if _ACTIVE_DIALOG is not None:
        try:
            _ACTIVE_DIALOG.close()
        except Exception:
            pass
    _ACTIVE_DIALOG = None
