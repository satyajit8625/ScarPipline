# -*- coding: utf-8 -*-
"""
DCC Window for Anim Export tool strictly conforming to UI-01 - UI-07 and suite-wide consistency.
Directly aligns with Shader Tools and Skin Tools architecture.
"""

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
    create_popup_menu,
    ScarPopupMenu,
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

from ..controller import AnimIOController
from ..operations import discover_scene_assets
from ..api.camera import find_active_shot_camera, fix_or_create_shot_camera
from .settings_dialog import (
    show_alembic_settings,
    show_fbx_settings,
    confirm_and_reset_settings,
    get_anim_export_settings,
)
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
    """
    Unified Production Anim Export Window matching the Shader Tools and Skin Tools interaction model.
    """

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
        configure_window(self, (760, 560), (850, 650))
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

        # 1. Standard Brand Header [UI-02]
        header, _subtitle = create_brand_header(
            "ANIM EXPORT",
            "Automatic Alembic and FBX shot cache extraction",
            parent=self,
        )
        root.addWidget(header)

        # 2. Standard Operation Panel (matches Shader Tools / Skin Tools) [UI-03]
        op_panel, op_layout, _ = create_section_panel("Operation", accent="operation", parent=self)
        op_row = QtWidgets.QHBoxLayout()
        op_row.setContentsMargins(0, 0, 0, 0)
        op_row.setSpacing(INLINE_SPACING)

        lbl_mode = QtWidgets.QLabel("Format", self)
        lbl_mode.setFixedWidth(FORM_LABEL_WIDTH)
        lbl_mode.setStyleSheet("color: #D2D2D2; font-size: 11px; font-weight: 500;")

        self.format_combo = QtWidgets.QComboBox(self)
        self.format_combo.addItems(["Both (Alembic + FBX)", "Alembic (.abc)", "FBX (.fbx)"])
        configure_field(self.format_combo, minimum_width=180)

        self.operation_help = QtWidgets.QLabel(
            "Extract geometry point caches and character/camera takes into shot directory.", self
        )
        self.operation_help.setStyleSheet("color: #8A94A6; font-size: 11px;")
        self.operation_help.setWordWrap(True)

        op_row.addWidget(lbl_mode)
        op_row.addWidget(self.format_combo)
        op_row.addWidget(self.operation_help, 1)
        op_layout.addLayout(op_row)
        root.addWidget(op_panel)

        # 3. Meshes & Assets Table Panel (matches Shader Tools) [UI-03, UI-05]
        asset_panel, asset_layout, _ = create_section_panel("Shot Assets", accent="pipeline", parent=self)

        top_bar = QtWidgets.QHBoxLayout()
        self.count_badge = QtWidgets.QLabel("0 assets detected", self)
        self.count_badge.setObjectName("CountBadge")

        self.refresh_btn = create_button("Refresh Scene", role="secondary", parent=self)
        self.refresh_btn.setToolTip("Scan active Maya scene for rigs and cameras (Hotkey: F5)")

        self.settings_btn = create_button("Settings…", role="secondary", parent=self)
        self.settings_btn.setToolTip("Configure Alembic & FBX parameters")

        top_bar.addWidget(self.count_badge)
        top_bar.addStretch(1)
        top_bar.addWidget(self.refresh_btn)
        top_bar.addWidget(self.settings_btn)
        asset_layout.addLayout(top_bar)

        self.asset_table = create_data_table(
            ["Asset Name", "Export", "Status"],
            stretch_columns=(0,),
            fixed_columns={1: 75, 2: TABLE_STATUS_WIDTH + 30},
            extended_selection=True,
            parent=self,
        )
        self.asset_table.setToolTip("Tip: Double-click a Camera row to automatically standardize or create it.")
        asset_layout.addWidget(self.asset_table, 1)
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
        self.apply_button.setToolTip("Export shot caches to Alembic and FBX (Hotkey: Ctrl+Enter)")

        # Open Shot Folder Button (Initially hidden until export completes)
        self.open_folder_btn = create_button("Open Folder", role="secondary", parent=self)
        self.open_folder_btn.setVisible(False)
        self.open_folder_btn.setToolTip("Open destination shot root in Windows Explorer.")
        status_layout.insertWidget(0, self.open_folder_btn)

        root.addWidget(action_footer)

    def _connect(self):
        self.settings_btn.clicked.connect(self._open_settings_menu)
        self.refresh_btn.clicked.connect(self.refresh_scene_data)
        self.asset_table.cellDoubleClicked.connect(self._on_table_double_clicked)
        self.asset_table.cellClicked.connect(self._on_cell_clicked)
        self.open_folder_btn.clicked.connect(self._open_shot_folder)
        self.apply_button.clicked.connect(self._do_export)

    def keyPressEvent(self, event):
        """Keyboard accelerators: Ctrl+Enter (Export), F5 (Refresh), Escape (Close)."""
        if (event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter)) and (event.modifiers() & QtCore.Qt.ControlModifier):
            self._do_export()
            event.accept()
            return
        elif event.key() == QtCore.Qt.Key_F5:
            self.refresh_scene_data()
            event.accept()
            return
        elif event.key() == QtCore.Qt.Key_Escape:
            self.close()
            event.accept()
            return
        super(AnimIODialog, self).keyPressEvent(event)

    def _open_settings_menu(self):
        """Show the standardized ScarPopupMenu with Alembic Settings, FBX Settings, and Defaults."""
        menu = create_popup_menu(parent=self)

        act_alembic = menu.addAction("◇  Alembic Settings…")
        act_fbx = menu.addAction("◇  FBX Settings…")
        menu.addSeparator()
        act_reset = menu.addAction("↻  Reset to Default")

        action = menu.exec_below_widget(self.settings_btn, offset_y=5, align="right")

        if action == act_alembic:
            show_alembic_settings(parent=self)
        elif action == act_fbx:
            show_fbx_settings(parent=self)
        elif action == act_reset:
            if confirm_and_reset_settings(parent=self):
                self._set_message("All Alembic & FBX export settings restored to studio defaults.", "neutral")
                self._set_status("Settings Reset", "idle")

    def _on_cell_clicked(self, row, col):
        """Clicking the Export column cell toggles the checkbox cleanly."""
        if col == 1:
            check_item = self.asset_table.item(row, 1)
            if check_item:
                new_state = QtCore.Qt.Unchecked if check_item.checkState() == QtCore.Qt.Checked else QtCore.Qt.Checked
                check_item.setCheckState(new_state)

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

    @staticmethod
    def _item(text, color=None, alignment=QtCore.Qt.AlignLeft):
        item = QtWidgets.QTableWidgetItem(str(text))
        item.setTextAlignment(alignment | QtCore.Qt.AlignVCenter)
        if color:
            item.setForeground(QtGui.QColor(color))
        return item

    def refresh_scene_data(self):
        """Scan active Maya scene for shot identity, cameras, characters, props, and timeline range."""
        identity = parse_shot_scene_identity()

        self._resolved_shot_name = identity.get("shot_name") or "untitled_shot"
        self._resolved_shot_root = identity.get("export_dir") or ""
        is_unsaved = (self._resolved_shot_name.lower() in ("untitled_shot", "untitled_scene", "untitled"))

        target_cam_name = self._resolved_shot_name + "_CAM" if not is_unsaved else "Shot_CAM"
        cam_node = find_active_shot_camera(self._resolved_shot_name)
        self._resolved_camera = cam_node

        data = discover_scene_assets()

        # Elements Table: Camera + Scene Assets (all checked by default)
        assets = data.get("assets", []) or (data.get("characters", []) + data.get("props", []))
        seen_assets = set()
        clean_assets = []
        for a in assets:
            if a not in seen_assets:
                seen_assets.add(a)
                clean_assets.append(a)

        total = (1 if cam_node else 0) + len(clean_assets)
        self.count_badge.setText("{} assets detected".format(total))

        self.asset_table.setRowCount(0)
        row = 0

        # 1. Camera Row (Indicates status directly in the list!)
        if cam_node and cmds.objExists(cam_node):
            short_cam = cam_node.split("|")[-1]
            self.asset_table.insertRow(row)

            # Col 0: Asset Name
            item_cam_name = QtWidgets.QTableWidgetItem(short_cam)
            item_cam_name.setData(QtCore.Qt.UserRole, ("camera", cam_node))
            item_cam_name.setToolTip("Shot Camera: {}".format(cam_node))

            # Col 1: Export Checkbox
            item_cam_check = QtWidgets.QTableWidgetItem()
            item_cam_check.setCheckState(QtCore.Qt.Checked)
            item_cam_check.setTextAlignment(QtCore.Qt.AlignCenter)
            item_cam_check.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            item_cam_check.setToolTip("Include shot camera in export")

            self.asset_table.setItem(row, 0, item_cam_name)
            self.asset_table.setItem(row, 1, item_cam_check)

            # Col 2: Status (clean text matching Shader Tools & Skin Tools)
            if short_cam.lower() == target_cam_name.lower():
                item_cam_status = self._item("Ready", color=COLOR_STATUS_SUCCESS, alignment=QtCore.Qt.AlignCenter)
            else:
                item_cam_status = self._item("Rename Needed", color=COLOR_STATUS_WARNING, alignment=QtCore.Qt.AlignCenter)
            self.asset_table.setItem(row, 2, item_cam_status)
            row += 1
        elif not is_unsaved:
            # Missing standardized camera row
            self.asset_table.insertRow(row)
            item_cam_name = QtWidgets.QTableWidgetItem(target_cam_name)
            item_cam_name.setData(QtCore.Qt.UserRole, ("camera", None))
            item_cam_name.setToolTip("Camera '{}' not found in scene. Double-click to create.".format(target_cam_name))

            item_cam_check = QtWidgets.QTableWidgetItem()
            item_cam_check.setCheckState(QtCore.Qt.Unchecked)
            item_cam_check.setTextAlignment(QtCore.Qt.AlignCenter)
            item_cam_check.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)

            self.asset_table.setItem(row, 0, item_cam_name)
            self.asset_table.setItem(row, 1, item_cam_check)
            item_cam_status = self._item("Missing Camera", color=COLOR_STATUS_ERROR, alignment=QtCore.Qt.AlignCenter)
            self.asset_table.setItem(row, 2, item_cam_status)
            row += 1

        # 2. Scene Asset Rows
        for a in clean_assets:
            short = a.split("|")[-1]
            self.asset_table.insertRow(row)

            # Col 0: Asset Name
            item_name = QtWidgets.QTableWidgetItem(short)
            item_name.setData(QtCore.Qt.UserRole, ("asset", a))
            item_name.setToolTip("Scene Hierarchy: {}".format(a))

            # Col 1: Export Checkbox
            item_check = QtWidgets.QTableWidgetItem()
            item_check.setCheckState(QtCore.Qt.Checked)
            item_check.setTextAlignment(QtCore.Qt.AlignCenter)
            item_check.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            item_check.setToolTip("Include asset in export")

            self.asset_table.setItem(row, 0, item_name)
            self.asset_table.setItem(row, 1, item_check)
            item_status = self._item("Ready", color=COLOR_STATUS_SUCCESS, alignment=QtCore.Qt.AlignCenter)
            self.asset_table.setItem(row, 2, item_status)
            row += 1

        if total > 0:
            self._set_message("{} asset(s) ready for shot cache extraction.".format(total), "success")
        else:
            self._set_message("No assets detected. Select or import character/prop rigs.", "neutral")
        self._set_status("Ready", "idle")

    def _on_table_double_clicked(self, row, col):
        """Double clicking a camera row standardizes or creates the shot camera."""
        name_item = self.asset_table.item(row, 0)
        if not name_item:
            return
        data = name_item.data(QtCore.Qt.UserRole)
        if isinstance(data, (tuple, list)) and data[0] == "camera":
            src_node = data[1]
            self._fix_shot_camera(source_camera_node=src_node)

    def _fix_shot_camera(self, source_camera_node=None):
        """1-Click Camera Fix Helper: rename selected camera or create standardized shot camera."""
        try:
            fixed_cam = fix_or_create_shot_camera(self._resolved_shot_name, source_camera_node=source_camera_node)
            self.refresh_scene_data()
            self._set_message("Shot camera '{}' standardized successfully.".format(fixed_cam.split("|")[-1]), "success")
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
            check_item = self.asset_table.item(i, 1)
            name_item = self.asset_table.item(i, 0)
            if check_item and check_item.checkState() == QtCore.Qt.Checked and name_item:
                data = name_item.data(QtCore.Qt.UserRole)
                if isinstance(data, (tuple, list)):
                    atype, anode = data
                    if atype == "camera" and anode:
                        export_cam_node = anode
                    elif atype == "asset":
                        assets_to_export.append(anode)

        total_items = (1 if export_cam_node else 0) + len(assets_to_export)

        # Geo formats: Both / Alembic / FBX
        fmt_idx = self.format_combo.currentIndex()
        if fmt_idx == 0:
            geo_fmts = ("abc", "fbx")
        elif fmt_idx == 1:
            geo_fmts = ("abc",)
        else:
            geo_fmts = ("fbx",)

        # Read configured Alembic and FBX parameters
        user_cfg = get_anim_export_settings()
        abc_cfg = user_cfg.get("alembic", {})
        fbx_cfg = user_cfg.get("fbx", {})

        step = float(abc_cfg.get("step", 1.0))
        handles = int(abc_cfg.get("handles", 0))
        write_vel = bool(abc_cfg.get("write_velocities", True))
        write_uv = bool(abc_cfg.get("uvs", True))
        write_norm = bool(abc_cfg.get("normals", True))
        write_rend = bool(abc_cfg.get("renderable_only", True))
        write_vis = bool(abc_cfg.get("visibility", True))
        fbx_axis = str(fbx_cfg.get("up_axis", "Y-Up"))
        fbx_smooth = bool(fbx_cfg.get("smoothing_groups", True))
        fbx_ver = str(fbx_cfg.get("fbx_version", "FBX 2020"))
        fbx_tri = bool(fbx_cfg.get("triangulate", False))

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
                handles=handles,
                step=step,
                write_velocities=write_vel,
                uv_write=write_uv,
                write_normals=write_norm,
                renderable_only=write_rend,
                write_visibility=write_vis,
                fbx_up_axis=fbx_axis,
                fbx_smoothing_groups=fbx_smooth,
                fbx_version=fbx_ver,
                fbx_triangulate=fbx_tri,
                callbacks=callbacks,
            )
            if self._progress_popup:
                popup = self._progress_popup
                self._progress_popup = None
                popup.finish("Shot Caches Exported Successfully!", state="success")

            self._set_message("Exported shot caches successfully to '{}'!".format(res["target_dir"]), "success")
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
