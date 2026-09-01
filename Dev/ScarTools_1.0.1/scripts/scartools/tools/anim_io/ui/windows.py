# -*- coding: utf-8 -*-
"""
DCC Window for Anim Export tool strictly conforming to UI-01 - UI-07 and suite-wide consistency.
Directly aligns with Shader Tools and Skin Tools interaction model.
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

from ..controller import AnimIOController, AnimExportStateEnum
from ..api.camera import fix_or_create_shot_camera
from .settings_dialog import (
    show_alembic_settings,
    show_fbx_settings,
    confirm_and_reset_settings,
    get_anim_export_settings,
    close_settings_dialogs,
)
from scartools.framework import (
    open_in_file_manager,
    OperationCallbacks,
)
from scartools.framework.logging import emit_log


from scartools.framework import get_scene_fps
_get_scene_fps = get_scene_fps


class AnimIODialog(BaseToolDialog):
    """
    Unified Production Anim Export Window matching the Shader Tools and Skin Tools interaction model.
    """

    OBJECT_NAME = "ScarToolsAnimIODialog"
    TOOL_ID = "scartools_anim_io"
    WINDOW_TITLE = "Anim Export"

    FORMAT_DESCRIPTIONS = {
        0: "Geometry cache + animation/camera data",
        1: "Geometry point cache (.abc)",
        2: "Animation and camera data (.fbx)",
    }

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

        self._progress_popup = None
        self._script_job_ids = []

        self._build_ui()
        self._connect()
        apply_theme(self)
        self.rescan_scene()
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
        lbl_mode.setObjectName("FieldLabel")

        self.format_combo = QtWidgets.QComboBox(self)
        self.format_combo.addItems(["Both (Alembic + FBX)", "Alembic (.abc)", "FBX (.fbx)"])
        configure_field(self.format_combo, minimum_width=180)

        self.operation_help = QtWidgets.QLabel(self.FORMAT_DESCRIPTIONS[0], self)
        self.operation_help.setObjectName("Muted")
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

        self.rescan_btn = create_button("Rescan Scene", role="secondary", parent=self)
        self.rescan_btn.setToolTip("Scan active Maya scene for rigs and cameras (Hotkey: F5)")

        self.settings_btn = create_button("Settings ▾", role="secondary", parent=self)
        self.settings_btn.setToolTip("Configure Alembic & FBX export parameters")

        top_bar.addWidget(self.count_badge)
        top_bar.addStretch(1)
        top_bar.addWidget(self.rescan_btn)
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

        # Open Export Folder Button (Initially hidden until export completes)
        self.open_folder_btn = create_button("Open Export Folder", role="secondary", parent=self)
        self.open_folder_btn.setVisible(False)
        self.open_folder_btn.setToolTip("Open destination shot root in Windows Explorer.")
        status_layout.insertWidget(0, self.open_folder_btn)

        root.addWidget(action_footer)

    def _connect(self):
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        self.settings_btn.clicked.connect(self._open_settings_menu)
        self.rescan_btn.clicked.connect(self.rescan_scene)
        self.asset_table.cellDoubleClicked.connect(self._on_table_double_clicked)
        self.asset_table.cellClicked.connect(self._on_cell_clicked)
        self.open_folder_btn.clicked.connect(self._open_shot_folder)
        self.apply_button.clicked.connect(self._do_export)

    def _on_format_changed(self, index):
        self.operation_help.setText(self.FORMAT_DESCRIPTIONS.get(index, ""))
        fmt_map = {0: "both", 1: "abc", 2: "fbx"}
        self.controller.format_mode = fmt_map.get(index, "both")
        self.controller.recompute_state()
        self._update_footer_state()

    def keyPressEvent(self, event):
        """Keyboard accelerators: Ctrl+Enter (Export), F5 (Rescan), Escape (Close)."""
        if (event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter)) and (event.modifiers() & QtCore.Qt.ControlModifier):
            if self.apply_button.isEnabled():
                self._do_export()
            event.accept()
            return
        elif event.key() == QtCore.Qt.Key_F5:
            self.rescan_scene()
            event.accept()
            return
        elif event.key() == QtCore.Qt.Key_Escape:
            self.close()
            event.accept()
            return
        super(AnimIODialog, self).keyPressEvent(event)

    def _open_settings_menu(self):
        """Show the standardized ScarPopupMenu with Alembic Settings, FBX Settings, and Defaults."""
        if getattr(self, "_settings_menu_open", False):
            return

        self._settings_menu_open = True
        menu = create_popup_menu(parent=self)

        act_alembic = menu.addAction("Alembic Settings...")
        act_fbx = menu.addAction("FBX Settings...")
        menu.addSeparator()
        act_reset = menu.addAction("Reset to Default")

        def _on_about_to_hide():
            QtCore.QTimer.singleShot(150, lambda: setattr(self, "_settings_menu_open", False))

        menu.aboutToHide.connect(_on_about_to_hide)

        action = menu.exec_below_widget(self.settings_btn, offset_y=2, align="right")

        shot_ctx = {
            "shot_name": self.controller.shot_name,
            "shot_root": self.controller.shot_root,
            "start_frame": self.controller.start_frame,
            "end_frame": self.controller.end_frame,
        }

        if action == act_alembic:
            show_alembic_settings(parent=maya_main_window(), shot_context=shot_ctx)
        elif action == act_fbx:
            show_fbx_settings(parent=maya_main_window(), shot_context=shot_ctx)
        elif action == act_reset:
            if confirm_and_reset_settings(parent=maya_main_window()):
                self.controller.recompute_state()
                self._update_footer_state()

    def _on_cell_clicked(self, row, col):
        """Clicking the Export column cell toggles the checkbox cleanly."""
        if col == 1:
            check_item = self.asset_table.item(row, 1)
            if check_item and row < len(self.controller.assets):
                new_state = QtCore.Qt.Unchecked if check_item.checkState() == QtCore.Qt.Checked else QtCore.Qt.Checked
                check_item.setCheckState(new_state)
                self.controller.assets[row].checked = (new_state == QtCore.Qt.Checked)
                self.controller.recompute_state()
                self._update_footer_state()

    def _register_scene_callbacks(self):
        """Register Maya scene scriptJobs for automatic real-time UI updates on scene open, new, save, and timing changes."""
        self._unregister_scene_callbacks()
        if hasattr(cmds, "scriptJob") and not cmds.about(batch=True):
            for ev in ("SceneOpened", "NewSceneOpened", "SceneSaved", "playbackRangeChanged"):
                try:
                    jid = cmds.scriptJob(event=[ev, self.rescan_scene], runOnce=False)
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
        close_settings_dialogs()
        super(AnimIODialog, self).closeEvent(event)

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.ActivationChange and self.isActiveWindow():
            self.rescan_scene()
        super(AnimIODialog, self).changeEvent(event)

    def _update_footer_state(self):
        """Derive all footer text, status dot, and button enablement strictly from controller."""
        status_text, status_state, msg_text, msg_state, export_enabled = self.controller.get_status_info()

        self.status_label.setText(str(status_text))
        self.status_label.setProperty("state", status_state)
        self.status_dot.setProperty("state", status_state)
        repolish(self.status_label)
        repolish(self.status_dot)

        self.message_label.setText(str(msg_text))
        self.message_label.setProperty("state", msg_state)
        repolish(self.message_label)

        self.apply_button.setEnabled(export_enabled)

    @staticmethod
    def _item(text, color=None, alignment=QtCore.Qt.AlignLeft):
        item = QtWidgets.QTableWidgetItem(str(text))
        item.setTextAlignment(alignment | QtCore.Qt.AlignVCenter)
        if color:
            item.setForeground(QtGui.QColor(color))
        return item

    def rescan_scene(self):
        """Inspect active Maya scene and populate table and state."""
        self.controller.scan_scene()

        # Update Asset Count
        self.count_badge.setText(self.controller.get_asset_count_text())

        # Populate Table
        self.asset_table.setRowCount(len(self.controller.assets))
        for row, asset_item in enumerate(self.controller.assets):
            # Col 0: Name (Read-only, selectable)
            name_item = QtWidgets.QTableWidgetItem(asset_item.name)
            name_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            name_item.setData(QtCore.Qt.UserRole, (asset_item.item_type, asset_item.node))
            name_item.setToolTip("{}: {}".format(asset_item.details, asset_item.node or "Not in scene"))

            # Col 1: Checkbox
            check_item = QtWidgets.QTableWidgetItem()
            check_item.setCheckState(QtCore.Qt.Checked if asset_item.checked else QtCore.Qt.Unchecked)
            check_item.setTextAlignment(QtCore.Qt.AlignCenter)
            check_item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            check_item.setToolTip("Include in export")

            # Col 2: Status (Read-only, centered)
            if asset_item.status_variant == "success":
                status_color = COLOR_STATUS_SUCCESS
            elif asset_item.status_variant == "warning":
                status_color = COLOR_STATUS_WARNING
            elif asset_item.status_variant == "error":
                status_color = COLOR_STATUS_ERROR
            else:
                status_color = COLOR_TEXT_MUTED

            status_item = self._item(asset_item.status, color=status_color, alignment=QtCore.Qt.AlignCenter)
            status_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)

            self.asset_table.setItem(row, 0, name_item)
            self.asset_table.setItem(row, 1, check_item)
            self.asset_table.setItem(row, 2, status_item)

        self._update_footer_state()

    def _on_table_double_clicked(self, row, col):
        """Double clicking a camera row standardizes or creates the shot camera."""
        name_item = self.asset_table.item(row, 0)
        if not name_item:
            return
        data = name_item.data(QtCore.Qt.UserRole)
        if isinstance(data, (tuple, list)) and data[0] == "camera":
            src_node = data[1]
            try:
                fixed_cam = fix_or_create_shot_camera(self.controller.shot_name, source_camera_node=src_node)
                self.rescan_scene()
                emit_log("Shot camera '{}' standardized.".format(fixed_cam.split("|")[-1]), level="SUCCESS", source="anim_io")
            except Exception as e:
                emit_log("Camera fix error: {}".format(e), level="WARNING", source="anim_io")

    def _open_shot_folder(self):
        """Open the resolved shot root directory in native OS file manager."""
        if self.controller.shot_root:
            opened = open_in_file_manager(self.controller.shot_root)
            if not opened:
                emit_log("Could not open directory: {}".format(self.controller.shot_root), level="WARNING", source="anim_io")

    def _do_export(self):
        """Execute export using internal export plan and atomic undo safety."""
        self.controller.recompute_state()
        if self.controller.state == AnimExportStateEnum.BLOCKED:
            return

        user_cfg = get_anim_export_settings()
        abc_cfg = user_cfg.get("alembic", {})
        fbx_cfg = user_cfg.get("fbx", {})

        custom_out = str(abc_cfg.get("output_path", "")).strip() or str(fbx_cfg.get("output_path", "")).strip()
        if custom_out and os.path.isdir(custom_out):
            out_dir = custom_out
        else:
            out_dir = self.controller.shot_root

        if not out_dir or not os.path.isdir(out_dir):
            cur_scene = cmds.file(q=True, sceneName=True)
            if cur_scene:
                from scartools.framework import parse_shot_scene_identity
                identity = parse_shot_scene_identity(cur_scene)
                out_dir = identity.get("export_dir")
                self.controller.shot_root = out_dir

        if not out_dir or not os.path.isdir(out_dir):
            emit_log("Invalid shot directory. Please save the scene.", level="ERROR", source="anim_io")
            return

        shot_name = self.controller.shot_name or "untitled_shot"
        start_f = self.controller.start_frame
        end_f = self.controller.end_frame
        fps = _get_scene_fps()

        # Build export parameters from export plan
        plan = self.controller.export_plan
        if not plan:
            emit_log("No assets selected in export plan.", level="WARNING", source="anim_io")
            return

        emit_log("Anim Export started for shot '{}' ({} assets selected)".format(shot_name, len(plan)), level="INFO", source="anim_io")

        # Read configured settings
        user_cfg = get_anim_export_settings()
        abc_cfg = user_cfg.get("alembic", {})
        fbx_cfg = user_cfg.get("fbx", {})

        # Frame range from settings if explicitly overridden, else scene timeline
        start_f = abc_cfg.get("start_frame") if abc_cfg.get("start_frame") is not None else self.controller.start_frame
        end_f = abc_cfg.get("end_frame") if abc_cfg.get("end_frame") is not None else self.controller.end_frame
        step = float(abc_cfg.get("step", 1.0))

        # Alembic flags
        write_uv = bool(abc_cfg.get("uvs", True))
        all_uv_sets = bool(abc_cfg.get("all_uv_sets", True))
        write_norm = bool(abc_cfg.get("normals", True))
        write_vis = bool(abc_cfg.get("visibility", True))
        write_face_sets = bool(abc_cfg.get("face_sets", True))
        write_color_sets = bool(abc_cfg.get("color_sets", False))
        auto_subd = bool(abc_cfg.get("auto_subd", False))
        write_rend = bool(abc_cfg.get("renderable_only", False))
        world_space = bool(abc_cfg.get("world_space", True))
        euler_filter = bool(abc_cfg.get("euler_filter", False))
        user_attributes = bool(abc_cfg.get("user_attributes", False))
        attribute_prefix = str(abc_cfg.get("attribute_prefix", "ABC_"))
        strip_namespaces = bool(abc_cfg.get("strip_namespaces", True))
        data_format = str(abc_cfg.get("data_format", "Ogawa"))

        # FBX flags
        fbx_bake_anim = bool(fbx_cfg.get("bake_animation", True))
        fbx_step = int(fbx_cfg.get("step", 1))
        fbx_resample = bool(fbx_cfg.get("resample", True))
        fbx_euler_filter = bool(fbx_cfg.get("euler_filter", False))
        fbx_constant_key_reducer = bool(fbx_cfg.get("constant_key_reducer", False))
        fbx_quaternion_mode = str(fbx_cfg.get("quaternion_mode", "Resample"))
        fbx_skin = bool(fbx_cfg.get("skin", True))
        fbx_blend_shapes = bool(fbx_cfg.get("blend_shapes", True))
        fbx_smooth = bool(fbx_cfg.get("smoothing_groups", True))
        fbx_tangents_binormals = bool(fbx_cfg.get("tangents_binormals", True))
        fbx_smooth_mesh = bool(fbx_cfg.get("smooth_mesh", False))
        fbx_tri = bool(fbx_cfg.get("triangulate", False))
        fbx_cameras = bool(fbx_cfg.get("cameras", True))
        fbx_lights = bool(fbx_cfg.get("lights", False))
        fbx_constraints = bool(fbx_cfg.get("constraints", False))
        fbx_input_connections = bool(fbx_cfg.get("input_connections", False))
        fbx_preserve_instances = bool(fbx_cfg.get("preserve_instances", False))
        fbx_units = str(fbx_cfg.get("units", "Centimeters"))
        fbx_axis = str(fbx_cfg.get("up_axis", "Y"))
        fbx_file_type = str(fbx_cfg.get("file_type", "Binary"))
        fbx_ver = str(fbx_cfg.get("fbx_version", "FBX 2020"))
        fbx_embed_media = bool(fbx_cfg.get("embed_media", False))
        fbx_strip_namespaces = bool(fbx_cfg.get("strip_namespaces", True))

        # Categorize plan nodes
        cam_node = None
        char_nodes = []
        prop_nodes = []
        for p in plan:
            emit_log("Export Plan: {} -> {}".format(p["name"], ", ".join(p["formats"])), level="INFO", source="anim_io")
            if p["type"] == "camera":
                cam_node = p["node"]
            elif p["type"] == "character":
                char_nodes.append(p["node"])
            else:
                prop_nodes.append(p["node"])

        geo_fmts = ("abc", "fbx") if self.controller.format_mode == "both" else ((self.controller.format_mode,))

        # Progress popup
        self._progress_popup = OperationProgressPopup(
            title="Anim Export - Caching Shot",
            parent=self.window(),
            unit="assets",
        )
        self._progress_popup.start("Exporting Shot Caches", total=len(plan))
        self.controller.state = AnimExportStateEnum.EXPORTING
        self._update_footer_state()

        def _on_progress(pct, msg):
            if self._progress_popup:
                self._progress_popup.update_progress(pct, message=str(msg))
            QtWidgets.QApplication.processEvents()

        callbacks = OperationCallbacks(progress_callback=_on_progress)

        try:
            from ..operations import export_shot_package
            res = export_shot_package(
                output_dir=out_dir,
                shot_name=shot_name,
                start_frame=start_f,
                end_frame=end_f,
                fps=fps,
                camera_node=cam_node,
                camera_format="fbx",
                character_nodes=char_nodes,
                character_formats=geo_fmts,
                prop_nodes=prop_nodes,
                prop_formats=geo_fmts,
                handles=0,
                step=step,
                write_velocities=True,
                uv_write=write_uv,
                all_uv_sets=all_uv_sets,
                write_normals=write_norm,
                renderable_only=write_rend,
                write_visibility=write_vis,
                write_face_sets=write_face_sets,
                write_color_sets=write_color_sets,
                auto_subd=auto_subd,
                world_space=world_space,
                euler_filter=euler_filter,
                user_attributes=user_attributes,
                attribute_prefix=attribute_prefix,
                strip_namespaces=strip_namespaces,
                data_format=data_format,
                fbx_bake_animation=fbx_bake_anim,
                fbx_step=fbx_step,
                fbx_resample=fbx_resample,
                fbx_euler_filter=fbx_euler_filter,
                fbx_constant_key_reducer=fbx_constant_key_reducer,
                fbx_quaternion_mode=fbx_quaternion_mode,
                fbx_skin=fbx_skin,
                fbx_blend_shapes=fbx_blend_shapes,
                fbx_smoothing_groups=fbx_smooth,
                fbx_tangents_binormals=fbx_tangents_binormals,
                fbx_smooth_mesh=fbx_smooth_mesh,
                fbx_triangulate=fbx_tri,
                fbx_cameras=fbx_cameras,
                fbx_lights=fbx_lights,
                fbx_constraints=fbx_constraints,
                fbx_input_connections=fbx_input_connections,
                fbx_preserve_instances=fbx_preserve_instances,
                fbx_units=fbx_units,
                fbx_up_axis=fbx_axis,
                fbx_file_type=fbx_file_type,
                fbx_version=fbx_ver,
                fbx_embed_media=fbx_embed_media,
                fbx_strip_namespaces=fbx_strip_namespaces,
                callbacks=callbacks,
            )
            if self._progress_popup:
                popup = self._progress_popup
                self._progress_popup = None
                popup.finish("Shot Caches Exported Successfully!", state="success")

            self.controller.last_export_result = res
            self.controller.state = AnimExportStateEnum.SUCCESS
            self._update_footer_state()
            self.open_folder_btn.setVisible(True)
            emit_log("Anim Export completed successfully.", level="SUCCESS", source="anim_io")
        except Exception as e:
            if self._progress_popup:
                popup = self._progress_popup
                self._progress_popup = None
                popup.finish("Export Failed", state="error")
            self.controller.state = AnimExportStateEnum.FAILED
            self._update_footer_state()
            emit_log("Anim Export failed: {}".format(e), level="ERROR", source="anim_io")


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
    close_settings_dialogs()
