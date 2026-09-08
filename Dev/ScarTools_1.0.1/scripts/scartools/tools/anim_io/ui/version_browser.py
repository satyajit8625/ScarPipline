# -*- coding: utf-8 -*-
"""Shot Versions Browser Dialog for Anim I/O.

Allows visual inspection of all exported versions (v001, v002, ...)
and 1-click downstream shot assembly/import.
"""

from __future__ import absolute_import, division, print_function

import os

from scartools.ui.qt import QtCore, QtWidgets, QtGui, maya_main_window
from scartools.ui.window import BaseToolDialog, register_window
from scartools.ui import (
    configure_window,
    configure_root_layout,
    configure_field,
    create_brand_header,
    create_section_panel,
    create_data_table,
    create_button,
    create_action_footer,
    apply_theme,
    FORM_LABEL_WIDTH,
    INLINE_SPACING,
    PRIMARY_BUTTON_WIDTH,
)
from scartools.framework import open_in_file_manager
from scartools.ui.progress import OperationProgressPopup
from scartools.framework.operations import OperationCallbacks
from scartools.framework.logging import emit_log

from ..api.manifest_builder import get_all_shot_versions, load_shot_manifest
from ..operations import import_shot_package


class ShotVersionsDialog(BaseToolDialog):
    """
    Dedicated dialog for inspecting all exported shot versions and assembling selected versions.
    """

    TOOL_ID = "scartools_shot_versions"

    def __init__(self, shot_dir=None, parent=None):
        parent = parent or maya_main_window()
        super(ShotVersionsDialog, self).__init__(tool_id=self.TOOL_ID, parent=parent)

        from scartools.framework import resolve_shot_root_dir
        self.shot_dir = resolve_shot_root_dir(shot_dir) if shot_dir else ""
        self.versions_data = []
        self.selected_version = None

        self.setWindowTitle("Shot Versions Browser")
        configure_window(self, (640, 500), (680, 620))

        self._build_ui()
        self._connect()
        apply_theme(self)

        if self.shot_dir and os.path.isdir(self.shot_dir):
            self.refresh_versions()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Brand Header
        header, _ = create_brand_header(
            "SHOT VERSIONS",
            "Browse and assemble exported shot cache versions",
            parent=self,
        )
        root.addWidget(header)

        # 2. Shot Path Panel
        path_panel, path_layout, _ = create_section_panel("Shot Directory", accent="pipeline", parent=self)
        path_row = QtWidgets.QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(INLINE_SPACING)

        self.path_edit = QtWidgets.QLineEdit(self)
        self.path_edit.setText(self.shot_dir)
        self.path_edit.setPlaceholderText("Select shot folder (e.g. PRT_SH_010)...")
        configure_field(self.path_edit)

        self.browse_btn = create_button("Browse...", role="secondary", parent=self)
        self.browse_btn.setFixedWidth(80)

        self.open_folder_btn = create_button("Explorer", role="secondary", parent=self)
        self.open_folder_btn.setFixedWidth(75)

        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(self.browse_btn)
        path_row.addWidget(self.open_folder_btn)
        path_layout.addLayout(path_row)
        root.addWidget(path_panel)

        # 3. Versions Table Panel
        ver_panel, ver_layout, _ = create_section_panel("Available Versions", accent="data", parent=self)
        self.table = create_data_table(
            ["Version", "Date / Time", "Exported By", "Formats", "Frames", "Camera", "Assets"],
            stretch_columns=(1, 2),
            fixed_columns={0: 75, 3: 85, 4: 90, 5: 65, 6: 65},
            extended_selection=False,
            parent=self,
        )
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        ver_layout.addWidget(self.table)
        root.addWidget(ver_panel, 1)

        # 4. Version Inspection Panel
        inspect_panel, inspect_layout, _ = create_section_panel("Version Details", accent="neutral", parent=self)
        self.details_label = QtWidgets.QLabel("Select a version above to inspect its contents.", self)
        self.details_label.setObjectName("Muted")
        self.details_label.setWordWrap(True)
        inspect_layout.addWidget(self.details_label)
        root.addWidget(inspect_panel)

        # 5. Action Footer
        (
            action_footer,
            self.message_label,
            self.import_button,
            self.status_dot,
            self.status_label,
            self.view_log_button,
            status_layout,
        ) = create_action_footer(
            "IMPORT SELECTED VERSION",
            message="Select a version to import into Maya.",
            parent=self,
            include_log=False,
        )
        self.import_button.setMinimumWidth(PRIMARY_BUTTON_WIDTH)
        self.import_button.setEnabled(False)
        root.addWidget(action_footer)

    def _connect(self):
        self.browse_btn.clicked.connect(self._browse_shot_dir)
        self.open_folder_btn.clicked.connect(self._open_shot_folder)
        self.path_edit.editingFinished.connect(self._on_path_edited)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        self.import_button.clicked.connect(self._do_import)

    def _browse_shot_dir(self):
        start = self.shot_dir if (self.shot_dir and os.path.isdir(self.shot_dir)) else ""
        chosen = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Shot Root Directory",
            start,
            QtWidgets.QFileDialog.ShowDirsOnly,
        )
        if chosen:
            from scartools.framework import resolve_shot_root_dir
            self.shot_dir = resolve_shot_root_dir(chosen)
            self.path_edit.setText(self.shot_dir)
            self.refresh_versions()

    def _open_shot_folder(self):
        if self.shot_dir and os.path.isdir(self.shot_dir):
            if self.selected_version:
                # Try to open specific version subfolder
                for sub in ("Alembic", "FBX"):
                    ver_sub = os.path.join(self.shot_dir, sub, self.selected_version)
                    if os.path.isdir(ver_sub):
                        open_in_file_manager(ver_sub)
                        return
            open_in_file_manager(self.shot_dir)

    def _on_path_edited(self):
        txt = self.path_edit.text().strip()
        from scartools.framework import resolve_shot_root_dir
        clean = resolve_shot_root_dir(txt) if txt else ""
        if clean != self.shot_dir:
            self.shot_dir = clean
            self.path_edit.setText(clean)
            self.refresh_versions()

    def refresh_versions(self):
        """Scan target directory and populate versions table."""
        self.table.setRowCount(0)
        self.versions_data = []
        self.selected_version = None
        self.import_button.setEnabled(False)
        self.details_label.setText("Select a version above to inspect its contents.")

        if not self.shot_dir or not os.path.isdir(self.shot_dir):
            self.message_label.setText("Directory does not exist.")
            self.status_dot.set_status("warning", "No Directory")
            return

        self.versions_data = get_all_shot_versions(self.shot_dir)
        if not self.versions_data:
            self.message_label.setText("No exported versions found in this shot directory.")
            self.status_dot.set_status("neutral", "0 Versions")
            return

        self.table.setRowCount(len(self.versions_data))
        for row, rec in enumerate(self.versions_data):
            v_name = rec.get("version", "")
            time_str = rec.get("timestamp", "")
            user_str = rec.get("exported_by", "")
            
            fmts = []
            if rec.get("has_alembic"):
                fmts.append("Alembic")
            if rec.get("has_fbx"):
                fmts.append("FBX")
            fmt_str = " + ".join(fmts) if fmts else "Manifest only"

            fr = rec.get("frame_range", {})
            start_f = fr.get("start", 0)
            end_f = fr.get("end", 0)
            frames_str = "{} - {}".format(start_f, end_f) if (start_f or end_f) else "N/A"

            has_cam = "Yes" if rec.get("camera") else "No"
            chars = rec.get("characters", [])
            props = rec.get("props", [])
            assets_str = "{}C / {}P".format(len(chars), len(props))

            item_v = QtWidgets.QTableWidgetItem(v_name)
            item_v.setTextAlignment(QtCore.Qt.AlignCenter)
            item_v.setFont(QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold))

            item_t = QtWidgets.QTableWidgetItem(time_str)
            item_u = QtWidgets.QTableWidgetItem(user_str)
            item_f = QtWidgets.QTableWidgetItem(fmt_str)
            item_fr = QtWidgets.QTableWidgetItem(frames_str)
            item_c = QtWidgets.QTableWidgetItem(has_cam)
            item_c.setTextAlignment(QtCore.Qt.AlignCenter)
            item_a = QtWidgets.QTableWidgetItem(assets_str)
            item_a.setTextAlignment(QtCore.Qt.AlignCenter)

            for col, item in enumerate((item_v, item_t, item_u, item_f, item_fr, item_c, item_a)):
                item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                self.table.setItem(row, col, item)

        # Select the latest (last) version by default
        self.table.selectRow(len(self.versions_data) - 1)
        self.message_label.setText("Found {} exported version(s).".format(len(self.versions_data)))
        self.status_dot.set_status("success", "Ready")

    def _on_selection_changed(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            self.selected_version = None
            self.import_button.setEnabled(False)
            self.details_label.setText("Select a version above to inspect its contents.")
            return

        row = selected_rows[0].row()
        if row < len(self.versions_data):
            rec = self.versions_data[row]
            self.selected_version = rec.get("version")
            self.import_button.setEnabled(True)
            self.import_button.setText("IMPORT {}".format(self.selected_version.upper()))

            # Format detailed description
            chars = [c.get("name") or os.path.basename(c.get("file", "")) for c in rec.get("characters", [])]
            props = [p.get("name") or os.path.basename(p.get("file", "")) for p in rec.get("props", [])]
            cam = rec.get("camera", {})
            cam_name = cam.get("name") or (os.path.basename(cam.get("file", "")) if cam else "None")

            lines = [
                "• Version: {} (Exported by {} on {})".format(rec.get("version"), rec.get("exported_by"), rec.get("timestamp")),
                "• Workstation: {} | FPS: {}".format(rec.get("workstation", "N/A"), rec.get("fps", 24.0)),
                "• Camera: {}".format(cam_name),
                "• Characters ({}): {}".format(len(chars), ", ".join(chars) if chars else "None"),
                "• Props ({}): {}".format(len(props), ", ".join(props) if props else "None"),
            ]
            notes = rec.get("metadata", {}).get("notes") or rec.get("notes")
            if notes:
                lines.append("• Notes: {}".format(notes))

            self.details_label.setText("\n".join(lines))

    def _on_double_click(self, row, column):
        self._do_import()

    def _do_import(self):
        if not self.selected_version or not self.shot_dir:
            return

        ver = self.selected_version
        popup = OperationProgressPopup(
            title="Importing {}".format(ver.upper()),
            parent=self.window(),
            unit="pct",
        )
        popup.start("Assembling Shot Scene (Version {})...".format(ver), total=100)

        def _on_progress(pct, msg, **kwargs):
            popup.update_progress(int(pct), message=str(msg))
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 50)

        callbacks = OperationCallbacks(
            progress_callback=_on_progress,
            log_callback=lambda m: emit_log(m, level="INFO", source="ShotVersions"),
        )

        try:
            res = import_shot_package(
                package_dir_or_manifest=self.shot_dir,
                version=ver,
                callbacks=callbacks,
            )
            popup.finish("Shot Version {} Assembled Successfully!".format(ver), state="success")
            self.message_label.setText("Successfully imported version {}.".format(ver))
            self.status_dot.set_status("success", "Imported")
            emit_log("Assembled shot version {} into scene.".format(ver), level="SUCCESS", source="ShotVersions")
        except Exception as e:
            popup.finish("Import Failed", state="error")
            self.message_label.setText("Import error: {}".format(e))
            self.status_dot.set_status("error", "Failed")
            emit_log("Import error for version {}: {}".format(ver, e), level="ERROR", source="ShotVersions")


_SHOT_VERSIONS_DIALOG = None


def show_shot_versions(shot_dir=None, parent=None):
    """Raise or create the singleton ShotVersionsDialog."""
    global _SHOT_VERSIONS_DIALOG
    from scartools.framework import resolve_shot_root_dir
    clean_dir = resolve_shot_root_dir(shot_dir) if shot_dir else ""

    if _SHOT_VERSIONS_DIALOG is not None:
        try:
            if clean_dir and os.path.isdir(clean_dir):
                _SHOT_VERSIONS_DIALOG.shot_dir = clean_dir
                _SHOT_VERSIONS_DIALOG.path_edit.setText(clean_dir)
                _SHOT_VERSIONS_DIALOG.refresh_versions()
            _SHOT_VERSIONS_DIALOG.show()
            _SHOT_VERSIONS_DIALOG.raise_()
            _SHOT_VERSIONS_DIALOG.activateWindow()
            return _SHOT_VERSIONS_DIALOG
        except Exception:
            _SHOT_VERSIONS_DIALOG = None

    _SHOT_VERSIONS_DIALOG = ShotVersionsDialog(shot_dir=clean_dir, parent=parent)
    register_window(ShotVersionsDialog.TOOL_ID, _SHOT_VERSIONS_DIALOG)

    def _on_destroyed(*_):
        global _SHOT_VERSIONS_DIALOG
        _SHOT_VERSIONS_DIALOG = None

    try:
        _SHOT_VERSIONS_DIALOG.destroyed.connect(_on_destroyed)
    except Exception:
        pass

    _SHOT_VERSIONS_DIALOG.show()
    _SHOT_VERSIONS_DIALOG.raise_()
    _SHOT_VERSIONS_DIALOG.activateWindow()
    return _SHOT_VERSIONS_DIALOG
