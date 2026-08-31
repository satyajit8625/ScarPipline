# -*- coding: utf-8 -*-
"""DCC Window for Anim Export tool strictly conforming to UI-01 - UI-07 and centralized framework."""

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
    OperationProgressPopup,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_PRIMARY_BLUE,
    COLOR_ACCENT_PIPELINE,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    COLOR_STATUS_ERROR,
    FONT_FAMILY_MONO,
)
from scartools.ui.controls import (
    create_toggle_switch,
)

from ..controller import AnimIOController
from ..operations import discover_scene_assets
from ..api.camera import find_active_shot_camera, fix_or_create_shot_camera
from scartools.framework import (
    open_in_file_manager,
    parse_shot_scene_identity,
    OperationCallbacks,
)


def _get_scene_fps():
    """Query active Maya scene FPS cleanly."""
    try:
        unit = cmds.currentUnit(query=True, time=True)
        fps_map = {
            "game": 15.0,
            "film": 24.0,
            "pal": 25.0,
            "ntsc": 30.0,
            "show": 48.0,
            "palf": 50.0,
            "ntscf": 60.0,
            "23.976fps": 23.976,
            "29.97fps": 29.97,
            "47.952fps": 47.952,
            "59.94fps": 59.94,
        }
        if unit in fps_map:
            return fps_map[unit]
        if unit.endswith("fps"):
            return float(unit[:-3])
    except Exception:
        pass
    return 24.0


class AnimIODialog(BaseToolDialog):
    """Ultra-Clean Automated Studio UI Dialog for Anim Export Tool."""

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
        configure_window(self, (720, 520), (840, 620))
        apply_window_icon(self)

        self._resolved_shot_name = "untitled_shot"
        self._resolved_shot_root = ""
        self._resolved_camera = None
        self._progress_popup = None
        self._script_job_ids = []

        self._build_ui()
        self._connect()
        apply_theme(self)
        self.refresh_scene_data()
        self._register_scene_callbacks()

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

        # 2. Shot & Pipeline Information (Read-Only Auto-Detection Card with Camera Fix Helper) [UI-03]
        info_panel, info_layout, _ = create_section_panel(
            "Shot Pipeline Context", accent="pipeline", parent=self
        )
        info_grid = QtWidgets.QGridLayout()
        info_grid.setHorizontalSpacing(16)
        info_grid.setVerticalSpacing(8)

        lbl_shot_title = QtWidgets.QLabel("Active Shot:", self)
        lbl_shot_title.setStyleSheet("color: {}; font-weight: bold;".format(COLOR_TEXT_MUTED))
        self.val_shot = QtWidgets.QLabel("Detecting...", self)
        self.val_shot.setStyleSheet("color: {}; font-weight: bold; font-size: 13px;".format(COLOR_TEXT_PRIMARY))

        lbl_cam_title = QtWidgets.QLabel("Shot Camera:", self)
        lbl_cam_title.setStyleSheet("color: {}; font-weight: bold;".format(COLOR_TEXT_MUTED))

        cam_box = QtWidgets.QHBoxLayout()
        cam_box.setSpacing(8)
        self.val_cam = QtWidgets.QLabel("Detecting...", self)
        self.val_cam.setStyleSheet("color: {}; font-weight: bold; font-size: 13px;".format(COLOR_PRIMARY_BLUE))
        self.fix_cam_btn = create_button("Fix Camera", role="secondary", parent=self)
        self.fix_cam_btn.setFixedHeight(24)
        self.fix_cam_btn.setVisible(False)
        self.fix_cam_btn.setToolTip("Rename selected camera or create the standardized shot camera.")
        cam_box.addWidget(self.val_cam)
        cam_box.addWidget(self.fix_cam_btn)
        cam_box.addStretch(1)

        lbl_range_title = QtWidgets.QLabel("Timeline Range:", self)
        lbl_range_title.setStyleSheet("color: {}; font-weight: bold;".format(COLOR_TEXT_MUTED))
        self.val_range = QtWidgets.QLabel("Detecting...", self)
        self.val_range.setStyleSheet("color: {}; font-weight: bold; font-size: 12px;".format(COLOR_ACCENT_PIPELINE))

        lbl_path_title = QtWidgets.QLabel("Target Shot Root:", self)
        lbl_path_title.setStyleSheet("color: {}; font-weight: bold;".format(COLOR_TEXT_MUTED))
        self.val_path = QtWidgets.QLabel("Detecting...", self)
        self.val_path.setStyleSheet("color: {}; font-family: {};".format(COLOR_TEXT_MUTED, FONT_FAMILY_MONO))
        self.val_path.setWordWrap(True)

        info_grid.addWidget(lbl_shot_title, 0, 0)
        info_grid.addWidget(self.val_shot, 0, 1)
        info_grid.addWidget(lbl_cam_title, 0, 2)
        info_grid.addLayout(cam_box, 0, 3)
        info_grid.addWidget(lbl_range_title, 1, 0)
        info_grid.addWidget(self.val_range, 1, 1, 1, 3)
        info_grid.addWidget(lbl_path_title, 2, 0)
        info_grid.addWidget(self.val_path, 2, 1, 1, 3)

        info_layout.addLayout(info_grid)
        root.addWidget(info_panel)

        # 3. Shot Assets to Export Data Table [UI-03, UI-05]
        asset_panel, asset_layout, _ = create_section_panel(
            "Shot Assets to Export", accent="data", parent=self
        )
        top_bar = QtWidgets.QHBoxLayout()
        self.count_badge = QtWidgets.QLabel("0 assets detected")
        self.count_badge.setObjectName("CountBadge")
        top_bar.addWidget(self.count_badge)
        top_bar.addStretch(1)

        fmt_lbl = QtWidgets.QLabel("Format:", self)
        self.geo_format_combo = QtWidgets.QComboBox(self)
        self.geo_format_combo.addItems(["Alembic (.abc)", "FBX (.fbx)", "Both (.abc + .fbx)"])
        self.geo_format_combo.setCurrentIndex(2)  # Default: Both
        configure_field(self.geo_format_combo, minimum_width=140)
        top_bar.addWidget(fmt_lbl)
        top_bar.addWidget(self.geo_format_combo)

        self.refresh_btn = create_button("Refresh Scene", role="secondary", parent=self)
        top_bar.addWidget(self.refresh_btn)
        asset_layout.addLayout(top_bar)

        self.asset_table = create_data_table(
            ["Asset Name", "Source Hierarchy", "Status"],
            stretch_columns=(0, 1),
            fixed_columns={2: TABLE_STATUS_WIDTH},
            extended_selection=True,
            minimum_height=180,
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

        # 4. Standard Action Footer [UI-06]
        (
            action_footer,
            self.message_label,
            self.apply_button,
            self.status_dot,
            self.status_label,
            self.view_log_button,
            status_layout,
        ) = create_action_footer(
            "EXPORT SHOT CACHES",
            message="Ready to export shot caches.",
            parent=self,
            include_log=False,
        )
        self.apply_button.setMinimumWidth(PRIMARY_BUTTON_WIDTH)

        # Open Shot Folder Button (Initially hidden until export completes)
        self.open_folder_btn = create_button("Open Folder", role="secondary", parent=self)
        self.open_folder_btn.setVisible(False)
        self.open_folder_btn.setToolTip("Open destination shot root in Windows Explorer.")
        status_layout.insertWidget(0, self.open_folder_btn)

        root.addWidget(action_footer)

    def _connect(self):
        self.refresh_btn.clicked.connect(self.refresh_scene_data)
        self.fix_cam_btn.clicked.connect(self._fix_shot_camera)
        self.open_folder_btn.clicked.connect(self._open_shot_folder)
        self.apply_button.clicked.connect(self._do_export)

    def _register_scene_callbacks(self):
        """Register Maya scene scriptJobs for automatic real-time UI updates on scene open, new, save, and timing changes."""
        self._unregister_scene_callbacks()
        if hasattr(cmds, "scriptJob") and not cmds.about(batch=True):
            for ev in ("SceneOpened", "NewSceneOpened", "SceneSaved", "playbackRangeChanged"):
                try:
                    jid = cmds.scriptJob(event=[ev, self.refresh_scene_data], runOnce=False)
                    self._script_job_ids.append(jid)
                except Exception:
                    pass

    def _unregister_scene_callbacks(self):
        """Cleanly remove all registered scriptJobs upon dialog close."""
        for jid in getattr(self, "_script_job_ids", []):
            try:
                if hasattr(cmds, "scriptJob") and cmds.scriptJob(exists=jid):
                    cmds.scriptJob(kill=jid, force=True)
            except Exception:
                pass
        self._script_job_ids = []

    def closeEvent(self, event):
        self._unregister_scene_callbacks()
        super(AnimIODialog, self).closeEvent(event)

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.ActivationChange and self.isActiveWindow():
            self.refresh_scene_data()
        super(AnimIODialog, self).changeEvent(event)

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

    def refresh_scene_data(self):
        """Scan active Maya scene for shot identity, cameras, characters, props, and timeline range."""
        identity = parse_shot_scene_identity()

        self._resolved_shot_name = identity.get("shot_name") or "untitled_shot"
        self._resolved_shot_root = identity.get("export_dir") or ""
        is_unsaved = (self._resolved_shot_name.lower() in ("untitled_shot", "untitled_scene", "untitled"))

        # Find camera with sanity check
        target_cam_name = self._resolved_shot_name + "_CAM" if not is_unsaved else "Shot_CAM"
        cam_node = find_active_shot_camera(self._resolved_shot_name)
        self._resolved_camera = cam_node

        if cam_node:
            short_cam = cam_node.split("|")[-1]
            if short_cam.lower() == target_cam_name.lower():
                self.val_cam.setText(target_cam_name)
                self.val_cam.setStyleSheet("color: {}; font-weight: bold; font-size: 13px;".format(COLOR_PRIMARY_BLUE))
                self.fix_cam_btn.setVisible(False)
            else:
                self.val_cam.setText(short_cam + " (Rename needed)")
                self.val_cam.setStyleSheet("color: {}; font-weight: bold; font-size: 12px;".format(COLOR_STATUS_WARNING))
                self.fix_cam_btn.setVisible(True)
                self.fix_cam_btn.setText("Fix to " + target_cam_name)
        else:
            self.val_cam.setText("Missing ('{}')".format(target_cam_name))
            self.val_cam.setStyleSheet("color: {}; font-weight: bold; font-size: 12px;".format(COLOR_STATUS_ERROR))
            self.fix_cam_btn.setVisible(True)
            self.fix_cam_btn.setText("Create " + target_cam_name)

        if is_unsaved:
            self.val_shot.setText(self._resolved_shot_name + " (Unsaved Scene)")
            self.val_shot.setStyleSheet("color: {}; font-weight: bold; font-size: 13px;".format(COLOR_STATUS_WARNING))
        else:
            self.val_shot.setText(self._resolved_shot_name)
            self.val_shot.setStyleSheet("color: {}; font-weight: bold; font-size: 13px;".format(COLOR_TEXT_PRIMARY))

        self.val_path.setText(self._resolved_shot_root or "Active Maya Project / Current Scene Directory")

        # Timeline range - robust start/end bounds check
        start_f = 1001
        end_f = 1100
        try:
            if hasattr(cmds, "playbackOptions"):
                min_t = cmds.playbackOptions(q=True, minTime=True)
                max_t = cmds.playbackOptions(q=True, maxTime=True)
                if min_t is not None and max_t is not None:
                    start_f = int(min_t)
                    end_f = int(max_t)
                    if start_f > end_f:
                        start_f, end_f = end_f, start_f
        except Exception:
            pass

        total_frames = max(0, end_f - start_f + 1)
        self.val_range.setText("Frames {} to {} ({} frames)".format(start_f, end_f, total_frames))

        proj = identity.get("project")
        dept = identity.get("department") or "ANM"
        ver = identity.get("version_str") or "V001"
        if proj:
            self.header_subtitle.setText(
                "Project: {} | Shot: {} | Dept: {} | Scene: {}".format(
                    proj, self._resolved_shot_name, dept, ver
                )
            )
        else:
            self.header_subtitle.setText("Automatic Alembic (.abc) and FBX (.fbx) shot cache extraction")

        data = discover_scene_assets()

        # Elements Table: Camera + Scene Assets (all checked by default)
        assets = data.get("assets", []) or (data.get("characters", []) + data.get("props", []))
        # Deduplicate while preserving order
        seen_assets = set()
        clean_assets = []
        for a in assets:
            if a not in seen_assets:
                seen_assets.add(a)
                clean_assets.append(a)

        has_cam = bool(cam_node and cmds.objExists(cam_node))
        total = (1 if has_cam else 0) + len(clean_assets)
        self.count_badge.setText("{} assets detected".format(total))

        self.asset_table.setRowCount(0)
        row = 0

        # 1. Camera Row
        if has_cam:
            short_cam = cam_node.split("|")[-1]
            self.asset_table.insertRow(row)

            item_cam_name = QtWidgets.QTableWidgetItem(short_cam)
            item_cam_name.setData(QtCore.Qt.UserRole, ("camera", cam_node))
            item_cam_name.setCheckState(QtCore.Qt.Checked)

            item_cam_path = QtWidgets.QTableWidgetItem(cam_node)
            item_cam_status = QtWidgets.QTableWidgetItem("Ready")
            item_cam_status.setTextAlignment(QtCore.Qt.AlignCenter)
            item_cam_status.setForeground(QtGui.QColor(COLOR_STATUS_SUCCESS))

            self.asset_table.setItem(row, 0, item_cam_name)
            self.asset_table.setItem(row, 1, item_cam_path)
            self.asset_table.setItem(row, 2, item_cam_status)
            row += 1

        # 2. Scene Asset Rows
        for a in clean_assets:
            short = a.split("|")[-1]
            self.asset_table.insertRow(row)

            item_name = QtWidgets.QTableWidgetItem(short)
            item_name.setData(QtCore.Qt.UserRole, ("asset", a))
            item_name.setCheckState(QtCore.Qt.Checked)

            item_path = QtWidgets.QTableWidgetItem(a)
            item_status = QtWidgets.QTableWidgetItem("Ready")
            item_status.setTextAlignment(QtCore.Qt.AlignCenter)
            item_status.setForeground(QtGui.QColor(COLOR_STATUS_SUCCESS))

            self.asset_table.setItem(row, 0, item_name)
            self.asset_table.setItem(row, 1, item_path)
            self.asset_table.setItem(row, 2, item_status)
            row += 1

    def _fix_shot_camera(self):
        """1-Click Camera Fix Helper: rename selected camera or create standardized shot camera."""
        try:
            fixed_cam = fix_or_create_shot_camera(self._resolved_shot_name)
            self.refresh_scene_data()
            self._set_message("Shot camera '{}' configured successfully.".format(fixed_cam.split("|")[-1]), "neutral")
            self._set_status("Camera Fixed", "idle")
        except Exception as e:
            self._set_message("Camera fix error: {}".format(e), "warning")

    def _open_shot_folder(self):
        """Open the resolved shot root directory in native OS file manager."""
        if self._resolved_shot_root:
            opened = open_in_file_manager(self._resolved_shot_root)
            if opened:
                self._set_message("Opened: {}".format(self._resolved_shot_root), "neutral")
            else:
                self._set_message("Could not open path: {}".format(self._resolved_shot_root), "warning")

    def _do_export(self):
        out_dir = self._resolved_shot_root
        if not out_dir or not os.path.isdir(out_dir):
            cur_scene = cmds.file(q=True, sceneName=True)
            if cur_scene:
                identity = parse_shot_scene_identity(cur_scene)
                out_dir = identity.get("export_dir")
                self._resolved_shot_root = out_dir

        if not out_dir or not os.path.isdir(out_dir):
            self._set_message("Could not resolve valid shot directory from active Maya file. Please save the scene.", "warning")
            self._set_status("Invalid Shot Root", "warning")
            return

        shot_name = self._resolved_shot_name or "untitled_shot"

        # Frame range directly from Maya playback slider
        start_f = 1001
        end_f = 1100
        try:
            if hasattr(cmds, "playbackOptions"):
                min_t = cmds.playbackOptions(q=True, minTime=True)
                max_t = cmds.playbackOptions(q=True, maxTime=True)
                if min_t is not None and max_t is not None:
                    start_f = int(min_t)
                    end_f = int(max_t)
                    if start_f > end_f:
                        start_f, end_f = end_f, start_f
        except Exception:
            pass

        fps = _get_scene_fps()

        # Selected elements from table
        assets_to_export = []
        export_cam_node = None
        for i in range(self.asset_table.rowCount()):
            item = self.asset_table.item(i, 0)
            if item and item.checkState() == QtCore.Qt.Checked:
                atype, anode = item.data(QtCore.Qt.UserRole)
                if atype == "camera":
                    export_cam_node = anode
                else:
                    assets_to_export.append(anode)

        vel = self.vel_toggle.is_checked()
        total_items = (1 if export_cam_node else 0) + len(assets_to_export)

        # Geo formats
        geo_idx = self.geo_format_combo.currentIndex()
        geo_fmts = ("abc",) if geo_idx == 0 else (("fbx",) if geo_idx == 1 else ("abc", "fbx"))

        # Launch Centralized OperationProgressPopup
        self._progress_popup = OperationProgressPopup(
            title="Anim Export - Caching Shot",
            parent=self.window(),
            unit="assets",
        )
        self._progress_popup.start("Exporting Shot Caches", total=total_items)

        def _on_progress(pct, msg):
            if self._progress_popup:
                self._progress_popup.update_progress(pct, message=str(msg))
            self._set_status("Exporting ({}%)".format(pct), "running")
            self._set_message(msg, "neutral")
            QtWidgets.QApplication.processEvents()

        callbacks = OperationCallbacks(
            progress_callback=_on_progress,
        )

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
                fps=fps,
                camera_node=export_cam_node,
                camera_format="fbx",
                character_nodes=assets_to_export,
                character_formats=geo_fmts,
                prop_nodes=[],
                prop_formats=geo_fmts,
                handles=0,
                step=1.0,
                write_velocities=vel,
                callbacks=callbacks,
            )
            if self._progress_popup:
                popup = self._progress_popup
                self._progress_popup = None
                popup.finish("Shot Caches Exported Successfully!", state="success")

            self._set_message("Exported shot caches successfully to '{}'!".format(res["target_dir"]), "neutral")
            self._set_status("Export Success", "idle")
            self.open_folder_btn.setVisible(True)
        except Exception as e:
            if self._progress_popup:
                popup = self._progress_popup
                self._progress_popup = None
                popup.finish("Export Failed", state="error")
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
