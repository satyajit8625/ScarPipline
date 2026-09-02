# -*- coding: utf-8 -*-
"""DCC Window for Movable Pivot tool strictly adhering to UI-01 - UI-07.

Provides interactive precision pivot manipulation, bounding-box matrix alignment,
component centroid snapping, and persistent node bookmarks.
"""

from __future__ import absolute_import, division, print_function

import maya.cmds as cmds

from scartools.ui.qt import QtCore, QtWidgets, QtGui, maya_main_window
from scartools.ui.window import BaseToolDialog, register_window
from scartools.ui import (
    FORM_LABEL_WIDTH,
    FORM_ACTION_WIDTH,
    INLINE_SPACING,
    FIELD_HEIGHT,
    PRIMARY_BUTTON_WIDTH,
    configure_window,
    configure_root_layout,
    configure_field,
    create_brand_header,
    create_section_panel,
    create_subheading,
    create_segmented_control,
    create_action_footer,
    create_button,
    apply_theme,
    repolish,
    COLOR_PRIMARY_BLUE,
    COLOR_ACCENT_PIPELINE,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    COLOR_STATUS_ERROR,
    FONT_FAMILY_MONO,
)

from .controller import MovablePivotController
from .operations import (
    move_pivot_to_center,
    move_pivot_to_world_origin,
    move_pivot_to_bbox,
    move_pivot_to_components,
    rotate_pivot_to_axes,
    snap_pivot_to_object,
    save_pivot_preset,
    apply_pivot_preset,
    delete_pivot_preset,
    reset_pivot,
)


_ACTIVE_DIALOG = None


class MovablePivotDialog(BaseToolDialog):
    """Studio Rigging Utility Dialog for Non-Destructive Pivot Editing."""

    OBJECT_NAME = "ScarToolsMovablePivotDialog"
    TOOL_ID = "scartools_movable_pivot"
    WINDOW_TITLE = "Movable Pivot"

    def __init__(self, parent=None):
        super(MovablePivotDialog, self).__init__(
            parent=parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        configure_window(self, (460, 680), (480, 740))

        self.controller = MovablePivotController()
        self._script_job_ids = []

        self._build_ui()
        self._connect()
        self.rescan_selection()
        self._register_scene_callbacks()
        apply_theme(self)

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Brand Header [UI-02]
        header, _ = create_brand_header(
            "MOVABLE PIVOT",
            "Non-destructive matrix pivot editing engine",
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
        scroll_layout.setSpacing(10)

        # === A. TARGET SECTION ===
        target_panel, target_layout, _ = create_section_panel("Target Object", accent="rig", parent=self)
        target_row = QtWidgets.QHBoxLayout()
        target_row.setSpacing(8)

        lbl_target = QtWidgets.QLabel("Active Node:")
        lbl_target.setObjectName("FieldLabel")
        lbl_target.setFixedWidth(FORM_LABEL_WIDTH + 15)

        self.target_edit = QtWidgets.QLineEdit()
        self.target_edit.setReadOnly(True)
        self.target_edit.setObjectName("MutedInput")
        configure_field(self.target_edit)

        self.btn_refresh = create_button("Refresh", role="secondary", fixed_width=75, parent=self)
        self.btn_refresh.setToolTip("Refresh active selection from Maya viewport")

        target_row.addWidget(lbl_target)
        target_row.addWidget(self.target_edit, 1)
        target_row.addWidget(self.btn_refresh)
        target_layout.addLayout(target_row)
        scroll_layout.addWidget(target_panel)

        # === B. POSITION SECTION ===
        pos_panel, pos_layout, _ = create_section_panel("Position", accent="rig", parent=self)

        # Quick Mode Buttons
        quick_grid = QtWidgets.QGridLayout()
        quick_grid.setSpacing(6)

        self.btn_pos_center = create_button("Center", role="secondary", parent=self)
        self.btn_pos_center.setToolTip("Move pivot to object center")
        self.btn_pos_component = create_button("Component", role="secondary", parent=self)
        self.btn_pos_component.setToolTip("Move pivot to selected vertex/edge/face centroid")
        self.btn_pos_object = create_button("Object", role="secondary", parent=self)
        self.btn_pos_object.setToolTip("Move pivot to object transformation origin")
        self.btn_pos_world = create_button("World Origin", role="secondary", parent=self)
        self.btn_pos_world.setToolTip("Move pivot to World (0, 0, 0)")

        quick_grid.addWidget(self.btn_pos_center, 0, 0)
        quick_grid.addWidget(self.btn_pos_component, 0, 1)
        quick_grid.addWidget(self.btn_pos_object, 1, 0)
        quick_grid.addWidget(self.btn_pos_world, 1, 1)
        pos_layout.addLayout(quick_grid)

        pos_layout.addWidget(create_subheading("Bounding Box Alignment", is_first=False))

        # Bounding Box Segmented Controls
        bbox_grid = QtWidgets.QGridLayout()
        bbox_grid.setSpacing(8)

        lbl_x = QtWidgets.QLabel("X Axis:")
        lbl_x.setObjectName("FieldLabel")
        lbl_x.setFixedWidth(50)
        self.seg_x = create_segmented_control(["Min", "Center", "Max"], default_index=1, parent=self)

        lbl_y = QtWidgets.QLabel("Y Axis:")
        lbl_y.setObjectName("FieldLabel")
        lbl_y.setFixedWidth(50)
        self.seg_y = create_segmented_control(["Min", "Center", "Max"], default_index=1, parent=self)

        lbl_z = QtWidgets.QLabel("Z Axis:")
        lbl_z.setObjectName("FieldLabel")
        lbl_z.setFixedWidth(50)
        self.seg_z = create_segmented_control(["Min", "Center", "Max"], default_index=1, parent=self)

        bbox_grid.addWidget(lbl_x, 0, 0)
        bbox_grid.addWidget(self.seg_x, 0, 1)
        bbox_grid.addWidget(lbl_y, 1, 0)
        bbox_grid.addWidget(self.seg_y, 1, 1)
        bbox_grid.addWidget(lbl_z, 2, 0)
        bbox_grid.addWidget(self.seg_z, 2, 1)
        pos_layout.addLayout(bbox_grid)

        self.btn_apply_bbox = create_button("Align to Bounding Box", role="secondary", parent=self)
        pos_layout.addWidget(self.btn_apply_bbox)
        scroll_layout.addWidget(pos_panel)

        # === C. ORIENTATION SECTION ===
        rot_panel, rot_layout, _ = create_section_panel("Orientation & Alignment", accent="rig", parent=self)

        row_rot1 = QtWidgets.QHBoxLayout()
        row_rot1.setSpacing(8)
        lbl_source = QtWidgets.QLabel("Source:")
        lbl_source.setObjectName("FieldLabel")
        lbl_source.setFixedWidth(FORM_LABEL_WIDTH)
        self.combo_rot_source = QtWidgets.QComboBox()
        self.combo_rot_source.addItems(["World Axes", "Face Normal", "Edge Tangent", "Selected Object"])
        configure_field(self.combo_rot_source)
        row_rot1.addWidget(lbl_source)
        row_rot1.addWidget(self.combo_rot_source, 1)
        rot_layout.addLayout(row_rot1)

        row_rot2 = QtWidgets.QHBoxLayout()
        row_rot2.setSpacing(8)

        lbl_pri = QtWidgets.QLabel("Primary:")
        lbl_pri.setObjectName("FieldLabel")
        lbl_pri.setFixedWidth(FORM_LABEL_WIDTH)
        self.combo_primary = QtWidgets.QComboBox()
        self.combo_primary.addItems(["+X", "-X", "+Y", "-Y", "+Z", "-Z"])
        configure_field(self.combo_primary)

        lbl_sec = QtWidgets.QLabel("Secondary:")
        lbl_sec.setObjectName("FieldLabel")
        lbl_sec.setFixedWidth(FORM_LABEL_WIDTH + 5)
        self.combo_secondary = QtWidgets.QComboBox()
        self.combo_secondary.addItems(["+Y", "-Y", "+Z", "-Z", "+X", "-X"])
        configure_field(self.combo_secondary)

        row_rot2.addWidget(lbl_pri)
        row_rot2.addWidget(self.combo_primary, 1)
        row_rot2.addWidget(lbl_sec)
        row_rot2.addWidget(self.combo_secondary, 1)
        rot_layout.addLayout(row_rot2)

        self.btn_match_orientation = create_button("Match Orientation", role="secondary", parent=self)
        self.btn_match_orientation.setToolTip("Align pivot coordinate axes non-destructively to chosen source")
        rot_layout.addWidget(self.btn_match_orientation)
        scroll_layout.addWidget(rot_panel)

        # === D. SNAP SECTION ===
        snap_panel, snap_layout, _ = create_section_panel("Snap Pivot", accent="rig", parent=self)
        snap_row = QtWidgets.QHBoxLayout()
        snap_row.setSpacing(6)

        self.btn_snap_pos = create_button("Snap Position", role="secondary", parent=self)
        self.btn_snap_rot = create_button("Snap Rotation", role="secondary", parent=self)
        self.btn_snap_all = create_button("Snap Transform", role="secondary", parent=self)

        snap_row.addWidget(self.btn_snap_pos)
        snap_row.addWidget(self.btn_snap_rot)
        snap_row.addWidget(self.btn_snap_all)
        snap_layout.addLayout(snap_row)
        scroll_layout.addWidget(snap_panel)

        # === E. PRESETS SECTION ===
        preset_panel, preset_layout, _ = create_section_panel("Pivot Presets & Bookmarks", accent="rig", parent=self)

        preset_select_row = QtWidgets.QHBoxLayout()
        preset_select_row.setSpacing(8)
        lbl_preset = QtWidgets.QLabel("Preset:")
        lbl_preset.setObjectName("FieldLabel")
        lbl_preset.setFixedWidth(FORM_LABEL_WIDTH)
        self.combo_presets = QtWidgets.QComboBox()
        configure_field(self.combo_presets)
        preset_select_row.addWidget(lbl_preset)
        preset_select_row.addWidget(self.combo_presets, 1)
        preset_layout.addLayout(preset_select_row)

        preset_btn_row = QtWidgets.QHBoxLayout()
        preset_btn_row.setSpacing(6)

        self.btn_add_preset = create_button("+ Save Preset", role="secondary", parent=self)
        self.btn_rename_preset = create_button("Rename", role="secondary", parent=self)
        self.btn_delete_preset = create_button("Delete", role="secondary", parent=self)
        self.btn_apply_preset = create_button("Apply Preset", role="secondary", parent=self)

        preset_btn_row.addWidget(self.btn_add_preset)
        preset_btn_row.addWidget(self.btn_rename_preset)
        preset_btn_row.addWidget(self.btn_delete_preset)
        preset_btn_row.addWidget(self.btn_apply_preset)
        preset_layout.addLayout(preset_btn_row)
        scroll_layout.addWidget(preset_panel)

        scroll.setWidget(scroll_content)
        root.addWidget(scroll, 1)

        # 3. Action Footer [UI-06]
        (
            action_footer,
            self.message_label,
            self.apply_button,
            self.status_dot,
            self.status_label,
            self.view_log_button,
            status_layout,
        ) = create_action_footer(
            "APPLY PIVOT",
            message="Ready to edit pivot.",
            parent=self,
            include_log=True,
        )

        self.btn_reset_pivot = create_button("Reset Pivot", role="secondary", parent=self)
        self.btn_reset_pivot.setToolTip("Restore original captured pivot or center bounding box")
        status_layout.insertWidget(0, self.btn_reset_pivot)

        root.addWidget(action_footer)

    def _connect(self):
        self.btn_refresh.clicked.connect(self.rescan_selection)

        # Position actions
        self.btn_pos_center.clicked.connect(lambda: self._exec_action(move_pivot_to_center))
        self.btn_pos_world.clicked.connect(lambda: self._exec_action(move_pivot_to_world_origin))
        self.btn_pos_object.clicked.connect(lambda: self._exec_action(move_pivot_to_center))
        self.btn_pos_component.clicked.connect(self._on_pos_component)
        self.btn_apply_bbox.clicked.connect(self._on_apply_bbox)

        # Orientation actions
        self.btn_match_orientation.clicked.connect(self._on_match_orientation)

        # Snap actions
        self.btn_snap_pos.clicked.connect(lambda: self._exec_action(lambda: snap_pivot_to_object(snap_pos=True, snap_rot=False)))
        self.btn_snap_rot.clicked.connect(lambda: self._exec_action(lambda: snap_pivot_to_object(snap_pos=False, snap_rot=True)))
        self.btn_snap_all.clicked.connect(lambda: self._exec_action(lambda: snap_pivot_to_object(snap_pos=True, snap_rot=True)))

        # Presets actions
        self.btn_add_preset.clicked.connect(self._on_add_preset)
        self.btn_apply_preset.clicked.connect(self._on_apply_preset)
        self.btn_delete_preset.clicked.connect(self._on_delete_preset)
        self.btn_rename_preset.clicked.connect(self._on_rename_preset)

        # Footer actions
        self.apply_button.clicked.connect(self._on_apply_bbox)
        self.btn_reset_pivot.clicked.connect(lambda: self._exec_action(reset_pivot))
        if self.view_log_button:
            self.view_log_button.clicked.connect(self._open_log_viewer)

    def _exec_action(self, func):
        try:
            success = func()
            self.rescan_selection()
            if success:
                self.status_label.setText("Success")
                self.status_dot.setState("idle")
                self.message_label.setText("Pivot updated successfully.")
            else:
                self.status_label.setText("Warning")
                self.status_dot.setState("warning")
                self.message_label.setText("Check selection or Global Log.")
        except Exception as e:
            self.status_label.setText("Error")
            self.status_dot.setState("error")
            self.message_label.setText(str(e))

    def _on_pos_component(self):
        source = "face_normal" if self.combo_rot_source.currentIndex() == 1 else "world"
        align = self.combo_rot_source.currentIndex() != 0
        self._exec_action(lambda: move_pivot_to_components(align_orientation=align, orientation_source=source))

    def _on_apply_bbox(self):
        modes = ["min", "center", "max"]
        x_m = modes[self.seg_x.current_index()]
        y_m = modes[self.seg_y.current_index()]
        z_m = modes[self.seg_z.current_index()]
        self._exec_action(lambda: move_pivot_to_bbox(x=x_m, y=y_m, z=z_m))

    def _on_match_orientation(self):
        pri = str(self.combo_primary.currentText())
        sec = str(self.combo_secondary.currentText())
        self._exec_action(lambda: rotate_pivot_to_axes(primary_axis=pri, secondary_axis=sec))

    def _on_add_preset(self):
        node = self.controller.active_node
        if not node:
            self.message_label.setText("Select an object to save a preset.")
            return

        text, ok = QtWidgets.QInputDialog.getText(
            self, "Save Pivot Preset", "Preset Name:", QtWidgets.QLineEdit.Normal, "Hinge_01"
        )
        if ok and text.strip():
            save_pivot_preset(nodes=[node], preset_name=text.strip())
            self.rescan_selection()
            self.message_label.setText("Preset '{}' saved.".format(text.strip()))

    def _on_apply_preset(self):
        cur = str(self.combo_presets.currentText()).strip()
        if cur:
            self._exec_action(lambda: apply_pivot_preset(nodes=[self.controller.active_node], preset_name=cur))

    def _on_delete_preset(self):
        cur = str(self.combo_presets.currentText()).strip()
        if cur:
            delete_pivot_preset(nodes=[self.controller.active_node], preset_name=cur)
            self.rescan_selection()

    def _on_rename_preset(self):
        cur = str(self.combo_presets.currentText()).strip()
        if not cur:
            return
        new_text, ok = QtWidgets.QInputDialog.getText(
            self, "Rename Preset", "New Name:", QtWidgets.QLineEdit.Normal, cur
        )
        if ok and new_text.strip():
            from .pivot_manager import rename_preset
            rename_preset(self.controller.active_node, cur, new_text.strip())
            self.rescan_selection()

    def _open_log_viewer(self):
        try:
            from scartools.ui.logs import show_log_viewer
            show_log_viewer(parent=maya_main_window())
        except Exception:
            pass

    def rescan_selection(self):
        """Update UI fields and presets from active Maya scene selection."""
        self.controller.refresh_selection()
        self.target_edit.setText(self.controller.get_target_display_name())

        # Update presets combo
        self.combo_presets.blockSignals(True)
        self.combo_presets.clear()
        for p in self.controller.available_presets:
            self.combo_presets.addItem(p.name)
        self.combo_presets.blockSignals(False)

        has_target = bool(self.controller.active_node)
        self.apply_button.setEnabled(has_target)
        self.btn_add_preset.setEnabled(has_target)
        self.btn_apply_preset.setEnabled(bool(self.controller.available_presets))
        self.btn_delete_preset.setEnabled(bool(self.controller.available_presets))
        self.btn_rename_preset.setEnabled(bool(self.controller.available_presets))

    def _register_scene_callbacks(self):
        self._unregister_scene_callbacks()
        if hasattr(cmds, "scriptJob") and not cmds.about(batch=True):
            try:
                jid = cmds.scriptJob(event=["SelectionChanged", self.rescan_selection], runOnce=False)
                self._script_job_ids.append(jid)
            except Exception:
                pass

    def _unregister_scene_callbacks(self):
        for jid in getattr(self, "_script_job_ids", []):
            try:
                if hasattr(cmds, "scriptJob") and cmds.scriptJob(exists=jid):
                    cmds.scriptJob(kill=jid, force=True)
            except Exception:
                pass
        self._script_job_ids = []

    def closeEvent(self, event):
        self._unregister_scene_callbacks()
        super(MovablePivotDialog, self).closeEvent(event)


def show_window():
    """Launch the Movable Pivot tool window singleton."""
    global _ACTIVE_DIALOG
    if _ACTIVE_DIALOG is not None:
        try:
            _ACTIVE_DIALOG.close()
            _ACTIVE_DIALOG.deleteLater()
        except Exception:
            pass
    _ACTIVE_DIALOG = MovablePivotDialog()
    register_window("scartools_movable_pivot", _ACTIVE_DIALOG)
    _ACTIVE_DIALOG.show()
    _ACTIVE_DIALOG.raise_()
    _ACTIVE_DIALOG.activateWindow()
    return _ACTIVE_DIALOG


def close_all_windows():
    """Close active Movable Pivot dialog instances."""
    global _ACTIVE_DIALOG
    if _ACTIVE_DIALOG is not None:
        try:
            _ACTIVE_DIALOG.close()
            _ACTIVE_DIALOG.deleteLater()
        except Exception:
            pass
        _ACTIVE_DIALOG = None
        return True
    return False
