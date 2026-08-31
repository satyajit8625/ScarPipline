# -*- coding: utf-8 -*-
"""DCC Window for Anim Export tool strictly conforming to UI-01 - UI-07."""

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

from ..controller import AnimIOController
from ..operations import discover_scene_assets
from ..api.camera import find_active_shot_camera
from scartools.framework.naming import parse_shot_scene_identity


class AnimIODialog(BaseToolDialog):
    """Dedicated Studio UI Dialog for Anim Export Tool."""

    OBJECT_NAME = "ScarToolsAnimIODialog"
    TOOL_ID = "scartools_anim_io"
    WINDOW_TITLE = "Anim Export"

    def __init__(self, parent=None):
        super(AnimIODialog, self).__init__(
            parent=parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.controller = AnimIOController()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        configure_window(self, (720, 580), (840, 680))
        apply_window_icon(self)

        self._resolved_shot_name = "untitled_shot"
        self._resolved_shot_root = ""
        self._resolved_camera = None

        self._build_ui()
        self._connect()
        apply_theme(self)
        self.refresh_scene_data()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Brand Header [UI-02]
        header, self.header_subtitle = create_brand_header(
            "ANIM EXPORT",
            "Automatic Alembic (.abc) and FBX (.fbx) shot cache extraction",
            parent=self,
        )
        root.addWidget(header)

        # 2. Shot & Pipeline Information (Read-Only Auto-Detection Card) [UI-03]
        info_panel, info_layout, _ = create_section_panel(
            "Shot Pipeline Context", accent="pipeline", parent=self
        )
        info_grid = QtWidgets.QGridLayout()
        info_grid.setHorizontalSpacing(16)
        info_grid.setVerticalSpacing(8)

        lbl_shot_title = QtWidgets.QLabel("Active Shot:", self)
        lbl_shot_title.setStyleSheet("color: #888888; font-weight: bold;")
        self.val_shot = QtWidgets.QLabel("Detecting...", self)
        self.val_shot.setStyleSheet("color: #E0E0E0; font-weight: bold; font-size: 13px;")

        lbl_cam_title = QtWidgets.QLabel("Shot Camera:", self)
        lbl_cam_title.setStyleSheet("color: #888888; font-weight: bold;")
        self.val_cam = QtWidgets.QLabel("Detecting...", self)
        self.val_cam.setStyleSheet("color: #4F94CD; font-weight: bold; font-size: 13px;")

        lbl_path_title = QtWidgets.QLabel("Target Shot Root:", self)
        lbl_path_title.setStyleSheet("color: #888888; font-weight: bold;")
        self.val_path = QtWidgets.QLabel("Detecting...", self)
        self.val_path.setStyleSheet("color: #A0A0A0; font-family: monospace;")
        self.val_path.setWordWrap(True)

        info_grid.addWidget(lbl_shot_title, 0, 0)
        info_grid.addWidget(self.val_shot, 0, 1)
        info_grid.addWidget(lbl_cam_title, 0, 2)
        info_grid.addWidget(self.val_cam, 0, 3)
        info_grid.addWidget(lbl_path_title, 1, 0)
        info_grid.addWidget(self.val_path, 1, 1, 1, 3)

        info_layout.addLayout(info_grid)
        root.addWidget(info_panel)

        # 3. Frame Range & Timing [UI-03, UI-04]
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
        root.addWidget(range_panel)

        # 4. Characters & Props Data Table [UI-03, UI-05]
        asset_panel, asset_layout, _ = create_section_panel(
            "Characters & Props to Export", accent="data", parent=self
        )
        top_bar = QtWidgets.QHBoxLayout()
        self.count_badge = QtWidgets.QLabel("0 assets detected")
        self.count_badge.setObjectName("CountBadge")
        top_bar.addWidget(self.count_badge)
        top_bar.addStretch(1)

        fmt_lbl = QtWidgets.QLabel("Format:", self)
        self.geo_format_combo = QtWidgets.QComboBox(self)
        self.geo_format_combo.addItems(["Alembic (.abc)", "FBX (.fbx)", "Both (.abc + .fbx)"])
        configure_field(self.geo_format_combo, minimum_width=140)
        top_bar.addWidget(fmt_lbl)
        top_bar.addWidget(self.geo_format_combo)

        self.refresh_btn = create_button("Refresh Scene", role="secondary", parent=self)
        self.select_all_btn = create_button("Select All", role="secondary", parent=self)
        top_bar.addWidget(self.refresh_btn)
        top_bar.addWidget(self.select_all_btn)
        asset_layout.addLayout(top_bar)

        self.asset_table = create_data_table(
            ["Asset Name", "Type", "Source Hierarchy", "Status"],
            stretch_columns=(0, 2),
            fixed_columns={1: 90, 3: TABLE_STATUS_WIDTH},
            extended_selection=True,
            minimum_height=160,
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

        root.addWidget(asset_panel, 1)

        # 5. Standard Action Footer [UI-06]
        (
            action_footer,
            self.message_label,
            self.apply_button,
            self.status_dot,
            self.status_label,
            self.view_log_button,
            _status_layout,
        ) = create_action_footer(
            "EXPORT SHOT CACHES",
            message="Ready to export shot caches.",
            parent=self,
            include_log=False,
        )
        self.apply_button.setMinimumWidth(PRIMARY_BUTTON_WIDTH)
        root.addWidget(action_footer)

    def _connect(self):
        self.range_mode.currentIndexChanged.connect(self._on_range_mode_changed)
        self.refresh_btn.clicked.connect(self.refresh_scene_data)
        self.select_all_btn.clicked.connect(self._select_all_table_rows)
        self.apply_button.clicked.connect(self._do_export)

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
        identity = parse_shot_scene_identity()

        self._resolved_shot_name = identity.get("shot_name") or "untitled_shot"
        self._resolved_shot_root = identity.get("export_dir") or ""

        # Find camera
        cam_node = find_active_shot_camera(self._resolved_shot_name)
        self._resolved_camera = cam_node

        cam_display = cam_node.split("|")[-1] if cam_node else "None (No shot camera found)"
        self.val_shot.setText(self._resolved_shot_name)
        self.val_cam.setText(cam_display)
        self.val_path.setText(self._resolved_shot_root or "Active Maya Project / Current Scene Directory")

        proj = identity.get("project")
        dept = identity.get("department") or "ANM"
        ver = identity.get("version_str") or "V001"
        if proj:
            self.header_subtitle.setText(
                "Project: {} | Shot: {} | Dept: {} | Scene: {}".format(
                    proj, self._resolved_shot_name, dept, ver
                )
            )

        data = discover_scene_assets()

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

    def _do_export(self):
        out_dir = self._resolved_shot_root
        if not out_dir or not os.path.isdir(out_dir):
            # Fallback to current scene directory or prompt
            cur_scene = cmds.file(q=True, sceneName=True)
            if cur_scene:
                identity = parse_shot_scene_identity(cur_scene)
                out_dir = identity.get("export_dir")
                self._resolved_shot_root = out_dir

        if not out_dir or not os.path.isdir(out_dir):
            self._set_message("Could not resolve valid shot directory from active Maya file.", "warning")
            self._set_status("Invalid Shot Root", "warning")
            return

        shot_name = self._resolved_shot_name or "untitled_shot"
        start_f = self.start_spin.value()
        end_f = self.end_spin.value()
        handles = self.handles_spin.value()

        # Camera
        cam_node = self._resolved_camera or find_active_shot_camera(shot_name)

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
            self._set_message("Exporting shot caches into Alembic/ and FBX/...", "neutral")
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
                camera_format="fbx",
                character_nodes=chars,
                character_formats=geo_fmts,
                prop_nodes=props,
                prop_formats=geo_fmts,
                handles=handles,
                write_velocities=vel,
            )
            self._set_message("Exported shot caches successfully to '{}'!".format(res["target_dir"]), "neutral")
            self._set_status("Export Success", "idle")
        except Exception as e:
            self._set_message("Export failed: {}".format(e), "warning")
            self._set_status("Export Failed", "error")


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
