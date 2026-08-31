# -*- coding: utf-8 -*-
"""DCC Window for Animation Export & Import Suite matching Skin Tools & Shader Tools architecture."""

from __future__ import absolute_import, division, print_function

import os
import maya.cmds as cmds

from scartools.ui.qt import QtCore, QtWidgets, QtGui, apply_window_icon, maya_main_window
from scartools.ui.window import BaseToolDialog, register_window
from scartools.ui import (
    FORM_LABEL_WIDTH,
    FORM_ACTION_WIDTH,
    INLINE_SPACING,
    FIELD_HEIGHT,
    TABLE_STATUS_WIDTH,
    PRIMARY_BUTTON_WIDTH,
    configure_window,
    configure_root_layout,
    configure_field,
    create_brand_header,
    create_operation_group,
    create_section_panel,
    create_data_table,
    create_action_footer,
    create_button,
    apply_theme,
    repolish,
)
from scartools.ui.controls import (
    create_segmented_control,
    create_toggle_switch,
)
from scartools.ui.widgets import (
    PathPickerWidget,
)

from ..controller import AnimIOController
from ..operations import discover_scene_assets, load_shot_manifest


class AnimIODialog(BaseToolDialog):
    """Main Studio UI Dialog for ScarTools Animation Export & Import Suite."""

    OBJECT_NAME = "ScarToolsAnimIODialog"
    TOOL_ID = "scartools_anim_io"
    WINDOW_TITLE = "Animation I/O Suite"

    def __init__(self, parent=None):
        super(AnimIODialog, self).__init__(
            parent=parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.controller = AnimIOController()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        configure_window(self, (760, 640), (840, 750))
        apply_window_icon(self)

        self._build_ui()
        self._connect()
        apply_theme(self)
        self.refresh_scene_data()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Brand Header
        header, self.header_subtitle = create_brand_header(
            "ANIMATION I/O SUITE",
            "Shot animation packaging, Alembic and FBX cache extraction, and scene assembly",
            parent=self,
        )
        root.addWidget(header)

        # 2. Operation Mode Group (Matching Skin Tools & Shader Tools)
        operation_group, self.operation_combo, self.operation_help = (
            create_operation_group(
                modes=["Export Shot", "Import & Assemble"],
                help_text="Choose an operation, configure shot parameters, then click the action button.",
                parent=self,
            )
        )
        root.addWidget(operation_group)

        # 3. Stacked Operation Pages
        self.stack = QtWidgets.QStackedWidget(self)
        root.addWidget(self.stack, 1)

        # ==============================================================
        # TAB 1: EXPORT PAGE
        # ==============================================================
        export_widget = QtWidgets.QWidget(self)
        export_layout = QtWidgets.QVBoxLayout(export_widget)
        export_layout.setContentsMargins(0, 0, 0, 0)
        export_layout.setSpacing(10)

        # A. Target Destination & Shot Context
        dest_panel, dest_layout, _ = create_section_panel(
            "Target Destination & Shot Context", accent="pipeline", parent=self
        )
        self.path_picker = PathPickerWidget(
            mode="directory",
            placeholder="Select target export folder...",
            parent=self,
        )
        dest_layout.addWidget(self.path_picker)

        shot_row = QtWidgets.QHBoxLayout()
        shot_row.setSpacing(INLINE_SPACING)
        shot_lbl = QtWidgets.QLabel("Shot Name:", self)
        shot_lbl.setFixedWidth(FORM_LABEL_WIDTH)
        self.shot_name_input = QtWidgets.QLineEdit(self)
        self.shot_name_input.setPlaceholderText("e.g. SQ01_SH010")
        self.shot_name_input.setText("SQ01_SH010")
        configure_field(self.shot_name_input)
        shot_row.addWidget(shot_lbl)
        shot_row.addWidget(self.shot_name_input, 1)

        cam_lbl = QtWidgets.QLabel("Camera:", self)
        cam_lbl.setFixedWidth(55)
        self.cam_combo = QtWidgets.QComboBox(self)
        configure_field(self.cam_combo)
        self.cam_format_combo = QtWidgets.QComboBox(self)
        self.cam_format_combo.addItems(["FBX (.fbx)", "Alembic (.abc)"])
        configure_field(self.cam_format_combo, minimum_width=110)
        shot_row.addWidget(cam_lbl)
        shot_row.addWidget(self.cam_combo, 1)
        shot_row.addWidget(self.cam_format_combo)

        dest_layout.addLayout(shot_row)
        export_layout.addWidget(dest_panel)

        # B. Frame Range & Timing
        range_panel, range_layout, _ = create_section_panel(
            "Frame Range & Timing", accent="pipeline", parent=self
        )
        range_row = QtWidgets.QHBoxLayout()
        range_row.setSpacing(INLINE_SPACING)

        self.range_mode = create_segmented_control(
            ["Timeline", "Custom"], current=0, accent="pipeline", parent=self
        )
        range_row.addWidget(self.range_mode)

        start_f = 1001
        end_f = 1100
        try:
            if hasattr(cmds, "playbackOptions"):
                start_f = int(cmds.playbackOptions(q=True, minTime=True) or 1001)
                end_f = int(cmds.playbackOptions(q=True, maxTime=True) or 1100)
        except Exception:
            pass

        start_lbl = QtWidgets.QLabel("Start:", self)
        self.start_spin = QtWidgets.QSpinBox(self)
        self.start_spin.setRange(-999999, 999999)
        self.start_spin.setValue(start_f)
        configure_field(self.start_spin)
        range_row.addWidget(start_lbl)
        range_row.addWidget(self.start_spin)

        end_lbl = QtWidgets.QLabel("End:", self)
        self.end_spin = QtWidgets.QSpinBox(self)
        self.end_spin.setRange(-999999, 999999)
        self.end_spin.setValue(end_f)
        configure_field(self.end_spin)
        range_row.addWidget(end_lbl)
        range_row.addWidget(self.end_spin)

        handles_lbl = QtWidgets.QLabel("Handles (±):", self)
        self.handles_spin = QtWidgets.QSpinBox(self)
        self.handles_spin.setRange(0, 100)
        self.handles_spin.setValue(5)
        configure_field(self.handles_spin)
        range_row.addWidget(handles_lbl)
        range_row.addWidget(self.handles_spin)

        range_layout.addLayout(range_row)
        export_layout.addWidget(range_panel)

        # C. Characters & Props Data Table (Matching Skin Tools data table)
        asset_panel, asset_layout, _ = create_section_panel(
            "Characters & Props to Export", accent="data", parent=self
        )
        top_bar = QtWidgets.QHBoxLayout()
        self.count_badge = QtWidgets.QLabel("0 assets detected")
        self.count_badge.setObjectName("CountBadge")
        top_bar.addWidget(self.count_badge)
        top_bar.addStretch(1)

        fmt_lbl = QtWidgets.QLabel("Cache Format:", self)
        self.geo_format_combo = QtWidgets.QComboBox(self)
        self.geo_format_combo.addItems(["Alembic (.abc)", "FBX (.fbx)", "Both (.abc + .fbx)"])
        configure_field(self.geo_format_combo, minimum_width=140)
        top_bar.addWidget(fmt_lbl)
        top_bar.addWidget(self.geo_format_combo)

        self.refresh_btn = create_button("Refresh Selection", role="secondary", parent=self)
        self.select_all_btn = create_button("Select All", role="secondary", parent=self)
        top_bar.addWidget(self.refresh_btn)
        top_bar.addWidget(self.select_all_btn)
        asset_layout.addLayout(top_bar)

        self.asset_table = create_data_table(
            ["Asset Name", "Type", "Source Hierarchy", "Status"],
            stretch_columns=(0, 2),
            fixed_columns={1: 90, 3: TABLE_STATUS_WIDTH},
            extended_selection=True,
            minimum_height=150,
            parent=self,
        )
        asset_layout.addWidget(self.asset_table, 1)

        # Velocity toggle
        vel_row = QtWidgets.QHBoxLayout()
        vel_lbl = QtWidgets.QLabel("Alembic Motion Blur Velocity Vectors", self)
        self.vel_toggle = create_toggle_switch(text="", checked=True, accent="pipeline", parent=self)
        vel_row.addWidget(vel_lbl, 1)
        vel_row.addWidget(self.vel_toggle)
        asset_layout.addLayout(vel_row)

        export_layout.addWidget(asset_panel, 1)
        self.stack.addWidget(export_widget)

        # ==============================================================
        # TAB 2: IMPORT / ASSEMBLE PAGE
        # ==============================================================
        import_widget = QtWidgets.QWidget(self)
        import_layout = QtWidgets.QVBoxLayout(import_widget)
        import_layout.setContentsMargins(0, 0, 0, 0)
        import_layout.setSpacing(10)

        in_panel, in_layout, _ = create_section_panel(
            "Load Shot Package", accent="pipeline", parent=self
        )
        self.import_path_picker = PathPickerWidget(
            mode="directory",
            placeholder="Select shot package directory containing shot_manifest.json...",
            parent=self,
        )
        in_layout.addWidget(self.import_path_picker)
        import_layout.addWidget(in_panel)

        info_panel, info_layout, _ = create_section_panel(
            "Shot Manifest Details", accent="pipeline", parent=self
        )
        self.manifest_summary = QtWidgets.QTextEdit(self)
        self.manifest_summary.setReadOnly(True)
        self.manifest_summary.setPlaceholderText("Select a shot package to preview camera, frame range, and asset lists...")
        self.manifest_summary.setMinimumHeight(140)
        info_layout.addWidget(self.manifest_summary)
        import_layout.addWidget(info_panel)

        opts_panel, opts_layout, _ = create_section_panel(
            "Downstream Assembly Options", accent="pipeline", parent=self
        )
        self.chk_time = QtWidgets.QCheckBox("Set Timeline Frame Range & Playback FPS", self)
        self.chk_time.setChecked(True)
        self.chk_cam = QtWidgets.QCheckBox("Import & Reference Shot Camera (Lock Transforms)", self)
        self.chk_cam.setChecked(True)
        self.chk_chars = QtWidgets.QCheckBox("Import Character Point Caches", self)
        self.chk_chars.setChecked(True)
        self.chk_props = QtWidgets.QCheckBox("Import Prop Point Caches & Transforms", self)
        self.chk_props.setChecked(True)
        opts_layout.addWidget(self.chk_time)
        opts_layout.addWidget(self.chk_cam)
        opts_layout.addWidget(self.chk_chars)
        opts_layout.addWidget(self.chk_props)
        import_layout.addWidget(opts_panel)
        import_layout.addStretch(1)

        self.stack.addWidget(import_widget)

        # 4. Standard Action Footer (Matching Skin Tools & Shader Tools)
        (
            action_footer,
            self.message_label,
            self.apply_button,
            self.status_dot,
            self.status_label,
            self.view_log_button,
            _status_layout,
        ) = create_action_footer(
            "EXPORT SHOT PACKAGE",
            message="Ready to package shot.",
            parent=self,
            include_log=False,
        )
        self.apply_button.setMinimumWidth(PRIMARY_BUTTON_WIDTH)
        root.addWidget(action_footer)

    def _connect(self):
        self.operation_combo.currentIndexChanged.connect(self._on_operation_changed)
        self.range_mode.currentIndexChanged.connect(self._on_range_mode_changed)
        self.refresh_btn.clicked.connect(self.refresh_scene_data)
        self.select_all_btn.clicked.connect(self._select_all_table_rows)
        self.import_path_picker.pathChanged.connect(self._on_import_path_changed)
        self.apply_button.clicked.connect(self._on_action_clicked)

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

    def _on_operation_changed(self, index):
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.apply_button.setText("EXPORT SHOT PACKAGE")
            self.operation_help.setText("Extract camera and geometry caches into a versioned shot directory.")
            self._set_message("Ready to package shot.", "neutral")
            self._set_status("Ready", "idle")
        else:
            self.apply_button.setText("ASSEMBLE SHOT SCENE")
            self.operation_help.setText("Import and assemble camera, frame range, and caches from shot_manifest.json.")
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
        """Scan active Maya scene for shot identity, cameras, characters, and props."""
        # 1. Automatic Shot Scene Identity Parsing
        from scartools.framework.naming import parse_shot_scene_identity
        identity = parse_shot_scene_identity()

        shot_name = identity.get("shot_name")
        if shot_name and shot_name != "untitled_scene":
            self.shot_name_input.setText(shot_name)

        export_dir = identity.get("export_dir")
        if export_dir and not self.path_picker.path():
            self.path_picker.set_path(export_dir)

        proj = identity.get("project")
        dept = identity.get("department") or "ANM"
        ver = identity.get("version_str") or "V001"
        if proj:
            self.header_subtitle.setText(
                "Project: {} | Shot: {} | Dept: {} | Scene: {}".format(
                    proj, shot_name, dept, ver
                )
            )

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

        # Characters & Props Table
        chars = data.get("characters", [])
        props = data.get("props", [])
        total = len(chars) + len(props)
        self.count_badge.setText("{} assets detected".format(total))

        self.asset_table.setRowCount(0)
        row = 0
        for c in chars:
            short = c.split("|")[-1]
            self.asset_table.insertRow(row)

            item_name = QtWidgets.QTableWidgetItem(short)
            item_name.setData(QtCore.Qt.UserRole, ("character", c))
            item_name.setCheckState(QtCore.Qt.Checked)

            item_type = QtWidgets.QTableWidgetItem("Character")
            item_type.setTextAlignment(QtCore.Qt.AlignCenter)

            item_path = QtWidgets.QTableWidgetItem(c)
            item_status = QtWidgets.QTableWidgetItem("Ready")
            item_status.setTextAlignment(QtCore.Qt.AlignCenter)

            self.asset_table.setItem(row, 0, item_name)
            self.asset_table.setItem(row, 1, item_type)
            self.asset_table.setItem(row, 2, item_path)
            self.asset_table.setItem(row, 3, item_status)
            row += 1

        for p in props:
            short = p.split("|")[-1]
            self.asset_table.insertRow(row)

            item_name = QtWidgets.QTableWidgetItem(short)
            item_name.setData(QtCore.Qt.UserRole, ("prop", p))
            item_name.setCheckState(QtCore.Qt.Checked)

            item_type = QtWidgets.QTableWidgetItem("Prop")
            item_type.setTextAlignment(QtCore.Qt.AlignCenter)

            item_path = QtWidgets.QTableWidgetItem(p)
            item_status = QtWidgets.QTableWidgetItem("Ready")
            item_status.setTextAlignment(QtCore.Qt.AlignCenter)

            self.asset_table.setItem(row, 0, item_name)
            self.asset_table.setItem(row, 1, item_type)
            self.asset_table.setItem(row, 2, item_path)
            self.asset_table.setItem(row, 3, item_status)
            row += 1

    def _select_all_table_rows(self):
        for i in range(self.asset_table.rowCount()):
            item = self.asset_table.item(i, 0)
            if item:
                item.setCheckState(QtCore.Qt.Checked)

    def _on_import_path_changed(self, path):
        """Read manifest and populate summary."""
        manifest = load_shot_manifest(path)
        if not manifest:
            self.manifest_summary.setHtml("<span style='color:#E57373;'>No valid shot_manifest.json found in this directory.</span>")
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
        <table style='width:100%; border-collapse: collapse; font-family: Segoe UI, sans-serif; font-size: 12px;'>
            <tr><td style='color:#AFAFAF; width:120px;'><b>Shot Name:</b></td><td style='color:#FFFFFF;'><b>{}</b></td></tr>
            <tr><td style='color:#AFAFAF;'><b>Frame Range:</b></td><td style='color:#FFFFFF;'>{} to {} (FPS: {})</td></tr>
            <tr><td style='color:#AFAFAF;'><b>Active Camera:</b></td><td style='color:#FFFFFF;'>{}</td></tr>
            <tr><td style='color:#AFAFAF;'><b>Characters:</b></td><td style='color:#FFFFFF;'>{} asset(s)</td></tr>
            <tr><td style='color:#AFAFAF;'><b>Props:</b></td><td style='color:#FFFFFF;'>{} asset(s)</td></tr>
            <tr><td style='color:#AFAFAF;'><b>Export Date:</b></td><td style='color:#FFFFFF;'>{}</td></tr>
        </table>
        """.format(shot_name, fr.get("start"), fr.get("end"), fps, cam, chars, props, date)
        self.manifest_summary.setHtml(html)
        self._set_message("Manifest loaded for shot '{}'.".format(shot_name), "neutral")
        self._set_status("Manifest Loaded", "idle")

    def _on_action_clicked(self):
        mode = self.operation_combo.currentIndex()
        if mode == 0:
            self._do_export()
        else:
            self._do_import()

    def _do_export(self):
        out_dir = self.path_picker.path()
        if not out_dir or not os.path.isdir(out_dir):
            self._set_message("Please specify a valid export directory.", "warning")
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

        # Selected assets from table
        chars = []
        props = []
        for i in range(self.asset_table.rowCount()):
            item = self.asset_table.item(i, 0)
            if item and item.checkState() == QtCore.Qt.Checked:
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
