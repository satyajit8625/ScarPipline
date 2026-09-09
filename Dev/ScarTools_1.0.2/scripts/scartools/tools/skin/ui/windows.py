# -*- coding: utf-8 -*-
"""Qt windows for Skin Tools.

Keeping this module separate ensures the reusable skin operations can be used
from maya.standalone and from other tools without importing Qt.
"""

from __future__ import print_function

import os
import time

import maya.cmds as cmds

from scartools.ui import (
    BaseToolDialog,
    CARD_SPACING,
    CLOSE_BUTTON_WIDTH,
    FORM_ACTION_WIDTH,
    FORM_LABEL_WIDTH,
    GROUP_SPACING,
    INLINE_SPACING,
    LOG_BUTTON_WIDTH,
    LogDialog,
    OperationProgressPopup,
    TABLE_STATUS_WIDTH,
    configure_field,
    configure_root_layout,
    configure_window,
    create_action_card,
    create_action_footer,
    create_brand_header,
    create_button,
    create_data_table,
    create_navigation_tabs,
    create_operation_group,
    create_section_panel,
    create_status_bar,
    repolish,
)
from scartools.ui.theme import apply as apply_theme

from ..operations import (
    EPSILON,
    SKIN_PACKAGE_FILENAME,
    VERSION,
    _commit_mirror_skin_changes,
    copy_skin_cluster,
    copy_skin_weights,
    _ensure_api_undo_command,
    _current_scene_folder_name,
    _import_directory_for_scene,
    _next_version_directory,
    _prepare_mirror_skin_change,
    _require_saved_scene,
    _scene_directory,
    _short_name,
    _skin_cluster,
    _skin_fn,
    _skin_influence_paths,
    _mesh_shape,
    _mesh_transform,
    _selected_vertex_indices,
    export_skin_package,
    import_skin_package,
    inspect_skin_health,
    inspect_skin_symmetry,
    mirror_skin_weights,
    mirror_skin_weights_from_selected,
    remove_unused_influences,
    select_skin_issue_vertices,
    selected_meshes,
)
try:
    from shiboken6 import isValid as _qt_is_valid
except Exception:
    try:
        from shiboken2 import isValid as _qt_is_valid
    except Exception:
        def _qt_is_valid(obj):
            return obj is not None


from scartools.ui.qt import (
    QtCore,
    QtGui,
    QtWidgets,
    apply_window_icon,
    maya_main_window,
)


class SkinImportExportPage(BaseToolDialog):
    """
    Single-page production UI.

    Workflow:
        1. Select meshes in Maya.
        2. Refresh Selection.
        3. Choose Export or Import from the operation dropdown.
        4. Choose a path using the integrated path row.
        5. Execute.

    Export and Import remain modes on this page. The parent window may
    provide top-level navigation to a separate Utilities page.
    Multiple selected meshes are automatically handled as a batch.
    """

    OBJECT_NAME = "ScarToolsSkinImportExportPage"
    TOOL_ID = "skin"

    def __init__(self, parent=None, embedded=False):
        super(SkinImportExportPage, self).__init__(
            parent if parent is not None else maya_main_window()
        )

        self._embedded = embedded
        if embedded:
            self.setWindowFlags(QtCore.Qt.Widget)

        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle("Skin Tools - Import / Export")
        apply_window_icon(self)
        if embedded:
            configure_window(self, (0, 0))
        else:
            configure_window(self, (760, 560), (820, 620))
        self._progress_popup = None

        self._build_ui()
        self._connect()
        apply_theme(self)
        self._refresh_meshes()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root, embedded=self._embedded)

        # Header -------------------------------------------------------
        # The tabbed host owns the shared header when this page is embedded.
        if not self._embedded:
            header, _subtitle = create_brand_header(
                "SKIN TOOLS",
                "SkinCluster weight export and import",
                parent=self,
            )
            root.addWidget(header)

        # Operation ----------------------------------------------------
        operation_group, self.operation_combo, _operation_help = (
            create_operation_group(
                help_text=(
                    "Choose an operation, then click the button to select the path."
                ),
                parent=self,
            )
        )
        root.addWidget(operation_group)

        # Meshes -------------------------------------------------------
        mesh_group, mesh_layout, _mesh_title = create_section_panel(
            "Meshes", accent="data", parent=self
        )

        top_row = QtWidgets.QHBoxLayout()

        self.mesh_count_label = QtWidgets.QLabel(
            "0 meshes selected"
        )
        self.mesh_count_label.setObjectName("CountBadge")

        top_row.addWidget(self.mesh_count_label)
        top_row.addStretch()

        self.refresh_button = create_button("Refresh Selection")
        self.clear_meshes_button = create_button("Clear")

        top_row.addWidget(self.refresh_button)
        top_row.addWidget(self.clear_meshes_button)

        mesh_layout.addLayout(top_row)

        # Mesh table ---------------------------------------------------
        # Deliberately simple 3-column layout:
        # Mesh | SkinCluster | Status
        # Long names are readable, columns resize intelligently, and
        # status is visually separated from the node names.
        self._syncing_maya_selection = False
        self.mesh_table = create_data_table(
            ["Mesh", "SkinCluster", "Status"],
            stretch_columns=(0, 1),
            fixed_columns={2: TABLE_STATUS_WIDTH},
            extended_selection=True,
            parent=self,
        )

        mesh_layout.addWidget(self.mesh_table)

        root.addWidget(mesh_group)

        # Production-safe defaults are deliberately not exposed as permanent
        # screen clutter.  They remain widgets so existing callbacks and API
        # behavior stay stable, but are fixed to the validated pipeline values.
        self.create_joints_checkbox = QtWidgets.QCheckBox(self)
        self.create_joints_checkbox.setChecked(True)
        self.create_joints_checkbox.hide()
        self.normalize_checkbox = QtWidgets.QCheckBox(self)
        self.normalize_checkbox.setChecked(True)
        self.normalize_checkbox.hide()
        self.sparse_checkbox = QtWidgets.QCheckBox(self)
        self.sparse_checkbox.setChecked(True)
        self.sparse_checkbox.hide()
        self.metadata_checkbox = QtWidgets.QCheckBox(self)
        self.metadata_checkbox.setChecked(True)
        self.metadata_checkbox.hide()

        # Stable workflow footer ---------------------------------------
        # The full progress bar lives in a temporary popup shown only while
        # an Export or Import operation is running.
        (
            action_footer,
            self.warning_label,
            self.execute_button,
            self.status_dot,
            self.status_label,
            self.view_log_button,
            _status_layout,
        ) = create_action_footer(
            "EXPORT SKIN WEIGHTS",
            parent=self,
        )
        root.addWidget(action_footer)

        # Log is intentionally NOT shown in the main window.
        # It opens only when the user clicks View Log.
        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText(
            "Operation details will appear here..."
        )

        self._update_mode_ui()

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------

    def _connect(self):
        self.operation_combo.currentIndexChanged.connect(
            self._update_mode_ui
        )

        self.refresh_button.clicked.connect(
            self._refresh_meshes
        )

        self.clear_meshes_button.clicked.connect(
            self._clear_meshes
        )

        # Selecting multiple rows in this table selects the same meshes
        # simultaneously in Maya's viewport/outliner.
        self.mesh_table.itemSelectionChanged.connect(
            self._select_selected_meshes_in_maya
        )

        self.execute_button.clicked.connect(
            self._execute
        )

        self.view_log_button.clicked.connect(
            self._show_log_dialog
        )


    # ------------------------------------------------------------------
    # Mode
    # ------------------------------------------------------------------

    def _is_export(self):
        return self.operation_combo.currentText() == "Export"

    def _update_mode_ui(self):
        exporting = self._is_export()

        if exporting:
            self.execute_button.setText(
                "EXPORT SKIN WEIGHTS"
            )

            self._set_warning(
                "Click Export to choose the skin-weight root folder. Each "
                "export creates a new v### folder inside the current Maya "
                "scene folder, so previous skin versions are never overwritten.",
                state="neutral"
            )

        else:
            self.execute_button.setText(
                "IMPORT SKIN WEIGHTS"
            )

            self._set_warning(
                "Click Import to choose the skin-weight root folder. The "
                "tool reads only the current Maya scene folder and automatically "
                "uses its latest v### skin version.",
                state="neutral"
            )

        self._refresh_mesh_status_only()
        self._update_operation_colors()

    def _update_operation_colors(self):
        """
        Switch the primary button's accent color between Export (blue) and
        Import (green) using a Qt dynamic property, so the *same* stylesheet
        rules defined once in _apply_style() apply consistently — no second
        stylesheet, no size/padding drift between modes.
        """
        mode = "export" if self._is_export() else "import"

        self.execute_button.setProperty("mode", mode)
        self.execute_button.style().unpolish(self.execute_button)
        self.execute_button.style().polish(self.execute_button)

    # ------------------------------------------------------------------
    # Mesh list
    # ------------------------------------------------------------------

    def _refresh_meshes(self):
        self.mesh_table.setRowCount(0)

        meshes = selected_meshes()

        # selected_meshes() reads Maya's complete current selection, so
        # multiple viewport-selected meshes are retained as a batch.
        for mesh in meshes:
            self._add_mesh_row(mesh)

        self._update_mesh_count()
        self._update_warning()
        self._reset_progress_panel()

        if self.mesh_table.rowCount():
            self.mesh_table.selectAll()

        self._log(
            "Selection refreshed: {} mesh(es).".format(len(meshes))
        )

    def _add_mesh_row(self, mesh):
        skin = _skin_cluster(mesh)
        row = self.mesh_table.rowCount()

        self.mesh_table.insertRow(row)

        mesh_item = QtWidgets.QTableWidgetItem(_short_name(mesh))
        mesh_item.setData(QtCore.Qt.UserRole, mesh)
        mesh_item.setToolTip(mesh)
        mesh_item.setTextAlignment(
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
        )

        skin_item = QtWidgets.QTableWidgetItem(
            _short_name(skin) if skin else "—"
        )
        skin_item.setToolTip(skin if skin else "No skinCluster")
        skin_item.setTextAlignment(
            QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
        )

        status_item = QtWidgets.QTableWidgetItem(
            "SKINNED" if skin else "NO SKIN"
        )
        status_item.setTextAlignment(QtCore.Qt.AlignCenter)
        status_item.setFont(
            QtGui.QFont("Arial", 9, QtGui.QFont.Bold)
        )

        if skin:
            status_item.setForeground(QtGui.QColor("#72d6aa"))
        else:
            status_item.setForeground(QtGui.QColor("#f0bd68"))

        self.mesh_table.setItem(row, 0, mesh_item)
        self.mesh_table.setItem(row, 1, skin_item)
        self.mesh_table.setItem(row, 2, status_item)

    def _refresh_mesh_status_only(self):
        for row in range(self.mesh_table.rowCount()):
            mesh_item = self.mesh_table.item(row, 0)
            if not mesh_item:
                continue

            mesh = mesh_item.data(QtCore.Qt.UserRole)

            if not mesh or not cmds.objExists(mesh):
                continue

            skin = _skin_cluster(mesh)

            self.mesh_table.item(row, 1).setText(
                _short_name(skin) if skin else "—"
            )
            self.mesh_table.item(row, 1).setToolTip(
                skin if skin else "No skinCluster"
            )

            status_item = self.mesh_table.item(row, 2)
            status_item.setText(
                "SKINNED" if skin else "NO SKIN"
            )
            status_item.setForeground(
                QtGui.QColor("#72d6aa")
                if skin else QtGui.QColor("#f0bd68")
            )

        self._update_warning()

    def _update_mesh_count(self):
        count = self.mesh_table.rowCount()

        self.mesh_count_label.setText(
            "1 mesh selected" if count == 1
            else "{} meshes selected".format(count)
        )

    def _clear_meshes(self):
        self.mesh_table.setRowCount(0)
        self._update_mesh_count()
        self._update_warning()
        self._reset_progress_panel()
        self._log("Mesh list cleared.")

    def _selected_meshes_from_table(self):
        meshes = []

        for row in range(self.mesh_table.rowCount()):
            item = self.mesh_table.item(row, 0)

            if not item:
                continue

            mesh = item.data(QtCore.Qt.UserRole)

            if mesh and cmds.objExists(mesh):
                meshes.append(mesh)

        return meshes

    def _selected_table_meshes(self):
        """Return meshes represented by the currently selected table rows."""
        meshes = []

        for index in self.mesh_table.selectionModel().selectedRows():
            row = index.row()
            item = self.mesh_table.item(row, 0)

            if not item:
                continue

            mesh = item.data(QtCore.Qt.UserRole)

            if mesh and cmds.objExists(mesh):
                meshes.append(mesh)

        return meshes

    def _select_selected_meshes_in_maya(self):
        """
        Mirror the table's multi-selection into Maya.

        This is the important part of the viewport workflow:
        click one row, Ctrl-click more rows, or Shift-select a range and
        every selected row is selected simultaneously in Maya.
        """
        if self._syncing_maya_selection:
            return

        meshes = self._selected_table_meshes()

        self._syncing_maya_selection = True
        try:
            if meshes:
                cmds.select(meshes, replace=True)
            else:
                cmds.select(clear=True)
        finally:
            self._syncing_maya_selection = False

    # ------------------------------------------------------------------
    # Warning / validation
    # ------------------------------------------------------------------

    def _set_warning(self, text, state="caution"):
        """
        Set the warning label's text and its color state together.

        state:
            "caution"  — yellow. Something will be skipped or needs attention.
            "positive" — green. Confirms everything is in a good state.
            "error"    — red. A hard failure stopped the operation.
            "neutral"  — muted gray. Plain instructions, not a judgement call.
        """
        self.warning_label.setText(text)
        self.warning_label.setProperty("state", state)
        self.warning_label.style().unpolish(self.warning_label)
        self.warning_label.style().polish(self.warning_label)

    def _update_warning(self):
        meshes = self._selected_meshes_from_table()

        if not meshes:
            self._set_warning(
                "No meshes loaded. Select meshes in Maya and click Refresh Selection.",
                state="neutral"
            )
            return

        if self._is_export():
            no_skin = [
                _short_name(mesh)
                for mesh in meshes
                if not _skin_cluster(mesh)
            ]

            if no_skin:
                self._set_warning(
                    "{} mesh(es) have no skinCluster and will be skipped: {}".format(
                        len(no_skin),
                        ", ".join(no_skin)
                    ),
                    state="caution"
                )
            else:
                self._set_warning(
                    "All {} selected mesh(es) have a skinCluster.".format(
                        len(meshes)
                    ),
                    state="positive"
                )

        else:
            existing = [
                _short_name(mesh)
                for mesh in meshes
                if _skin_cluster(mesh)
            ]

            if existing:
                self._set_warning(
                    "{} mesh(es) already have a skinCluster and will be "
                    "skipped: {}".format(
                        len(existing),
                        ", ".join(existing)
                    ),
                    state="caution"
                )
            else:
                self._set_warning(
                    "No existing skinClusters detected.",
                    state="positive"
                )

    def _show_log_dialog(self):
        try:
            from scartools.ui.logs import show_global_log
            show_global_log(source="Skin Tools", parent=self)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log(self, message):
        self.log_box.appendPlainText(
            "[SkinTools] {}".format(message)
        )
        try:
            from scartools.framework.logging import emit_log
            emit_log(message, source="Skin Tools")
        except Exception:
            pass

        bar = self.log_box.verticalScrollBar()
        bar.setValue(bar.maximum())

        QtWidgets.QApplication.processEvents()


    def _set_status(self, text, state="idle"):
        """
        Set the status line's text and the dot's color together.

        state:
            "idle"    — gray. Nothing running.
            "running" — blue. A batch operation is in progress.
            "success" — green. The last operation finished cleanly.
            "error"   — red. The last operation hit a problem.
        """
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_dot.setProperty("state", state)
        repolish(self.status_label)
        repolish(self.status_dot)

    def _reset_progress_panel(self):
        self._close_progress_popup()
        self._set_status("Ready", state="idle")

    def _begin_progress(self, title, total):
        self._close_progress_popup()
        self._progress_popup = OperationProgressPopup(
            title="Skin Tools - Processing",
            parent=self.window(),
            unit="meshes",
        )
        self._progress_popup.start(title, total)
        self._set_status(title, state="running")

    def _set_progress_mesh(self, mesh_name):
        if self._progress_popup:
            self._progress_popup.set_current(mesh_name)

    def _progress(self, value, message=None, current=None, total=None):
        if self._progress_popup:
            self._progress_popup.update_progress(
                value, message=message, current=current, total=total
            )
        if message:
            self._set_status(message, state="running")
        QtWidgets.QApplication.processEvents()

    def _finish_progress(self, message, state="success"):
        if self._progress_popup:
            popup = self._progress_popup
            self._progress_popup = None
            popup.finish(message, state)
        self._set_status(message, state=state)

    def _close_progress_popup(self):
        if self._progress_popup:
            try:
                self._progress_popup.close()
                self._progress_popup.deleteLater()
            except Exception:
                pass
            self._progress_popup = None

    def _error(self, title, message):
        self._close_progress_popup()
        self._log("ERROR: {}".format(message))
        self._set_status("Error — see log", state="error")
        self._set_warning(message.split("\n")[0].strip(), state="error")
        QtWidgets.QMessageBox.critical(
            self,
            title,
            message
        )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _execute(self):
        meshes = self._selected_meshes_from_table()

        if not meshes:
            self._error(
                "Skin Tools",
                "No meshes selected."
            )
            return

        # Scene-classified storage requires a saved Maya file name.
        try:
            _require_saved_scene()
        except Exception as exc:
            self._error("Skin Tools", str(exc))
            return

        # Path is intentionally NOT stored in the main UI.
        # Export and import both ask for the shared skin-weight root folder.
        path = self._choose_operation_path()

        if not path:
            self._log("Operation cancelled.")
            return

        if self._is_export():
            self._execute_export(meshes, path)
        else:
            self._execute_import(meshes, path)

    def _choose_operation_path(self):
        """
        Choose the shared skin-weight root folder for both Export and Import.

        Export resolves the real data location as:
            <chosen root>/<stable rig name>/v###/skin_weights_package.json

        Version suffixes such as _v01 and _v02 resolve to the same stable rig
        folder. Import uses the latest v### automatically. Selecting a specific
        version folder such as v002 imports that version instead.
        """
        caption = (
            "Select Skin Weights Export Root Folder"
            if self._is_export()
            else "Select Skin Weights Import Root Folder"
        )

        result = cmds.fileDialog2(
            fileMode=3,
            caption=caption
        )

        if result:
            return os.path.normpath(result[0])

        return None

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _execute_export(self, meshes, path):
        valid = []
        skipped = []

        for mesh in meshes:
            if _skin_cluster(mesh):
                valid.append(mesh)
            else:
                skipped.append(mesh)

        if skipped:
            self._log(
                "WARNING: Skipping meshes without skinCluster:"
            )
            for mesh in skipped:
                self._log(
                    "  SKIP: {}".format(mesh)
                )

        if not valid:
            self._error(
                "Export Failed",
                "None of the selected meshes has a skinCluster."
            )
            return

        scene_dir = _scene_directory(path, create=True)
        scene_folder = _current_scene_folder_name()
        output_dir, version_name = _next_version_directory(
            scene_dir, create=True
        )

        self._log(
            "Exporting scene '{}' as version {} -> {}".format(
                scene_folder, version_name, output_dir
            )
        )

        output_path = os.path.join(output_dir, SKIN_PACKAGE_FILENAME)
        self._begin_progress("Exporting Packed Skin Weights", len(valid))
        self._log(
            "Packing {} mesh(es) into one JSON.".format(
                len(valid)
            )
        )

        def package_progress(value, message=""):
            completed = min(
                len(valid),
                max(1, int((int(value) / 100.0) * len(valid)) + 1),
            )
            self._progress(
                value,
                message,
                current=completed,
                total=len(valid),
            )

        try:
            export_skin_package(
                file_path=output_path,
                nodes=valid,
                log=self._log,
                progress=package_progress,
                sparse=self.sparse_checkbox.isChecked(),
                include_metadata=self.metadata_checkbox.isChecked(),
            )
            self._finish_progress(
                "Export complete: 1 packed JSON / {} meshes".format(len(valid)),
                state="success",
            )
            self._log(
                "DONE: {} mesh(es) packed -> {}".format(len(valid), output_path)
            )
        except Exception as exc:
            self._log("ERROR: Packed export failed -> {}".format(exc))
            try:
                if os.path.isdir(output_dir) and not os.listdir(output_dir):
                    os.rmdir(output_dir)
            except Exception:
                pass
            self._finish_progress("Packed export failed", state="error")

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def _execute_import(self, meshes, path):
        skinned = [mesh for mesh in meshes if _skin_cluster(mesh)]
        importable = [mesh for mesh in meshes if mesh not in skinned]

        if skinned:
            self._log(
                "WARNING: Skipping {} mesh(es) that already have a "
                "skinCluster:".format(len(skinned))
            )
            for mesh in skinned:
                self._log("  SKIP: {}".format(_short_name(mesh)))

        if not importable:
            self._error(
                "Import Failed",
                "All selected meshes already have a skinCluster, so there "
                "is nothing to import.\n\n"
                "Unbind or delete the existing skinCluster first if you "
                "want to re-import weights onto these meshes."
            )
            return

        meshes = importable

        if not os.path.isdir(path):
            self._error(
                "Import Failed",
                "The selected skin-weight root folder does not exist."
            )
            return

        jobs = []

        scene_dir = _scene_directory(path, create=False)

        if not os.path.isdir(scene_dir):
            self._error(
                "Import Failed",
                "No skin-weight folder exists for the current Maya scene.\n\n"
                "Expected folder:\n{}".format(scene_dir)
            )
            return

        import_dir, version_name = _import_directory_for_scene(
            scene_dir, requested_directory=path
        )

        if not import_dir:
            self._error(
                "Import Failed",
                "No skin-weight versions were found for the current Maya scene.\n\n"
                "Expected version folders such as v001, v002, v003 inside:\n{}".format(
                    scene_dir
                )
            )
            return

        self._log(
            "Using skin version {} from: {}".format(
                version_name, import_dir
            )
        )

        package_path = os.path.join(import_dir, SKIN_PACKAGE_FILENAME)

        if not os.path.isfile(package_path):
            self._error(
                "Import Failed",
                "The selected snapshot does not contain {}.\n\n"
                "Legacy individual mesh JSON files are not supported. Re-export "
                "the asset as one packed snapshot with ScarTools 4.8 or newer."
                .format(SKIN_PACKAGE_FILENAME)
            )
            return

        for mesh in meshes:
            jobs.append((mesh, package_path))

        if not jobs:
            self._error(
                "Import Failed",
                "No matching mesh records were found in the packed skin package."
            )
            return

        self._begin_progress("Importing Skin Weights", len(jobs))
        self._log(
            "Starting import: {} mesh(es).".format(
                len(jobs)
            )
        )

        try:
            def package_progress(value, message=""):
                completed = min(
                    len(jobs), int((int(value) / 100.0) * len(jobs))
                )
                self._progress(
                    value, message, current=completed, total=len(jobs)
                )

            result = import_skin_package(
                file_path=package_path,
                nodes=[mesh for mesh, _json_path in jobs],
                force=False,
                create_missing_joints=True,
                normalize=True,
                validate_topology=True,
                use_undo=True,
                log=self._log,
                progress=package_progress,
            )
            imported_count = len(result["skins"])
            self._finish_progress(
                "Import complete: {} mesh(es)".format(imported_count),
                state="success",
            )
            self._log(
                "Import finished. {} successful in one undo step.".format(
                    imported_count
                )
            )
        except Exception as exc:
            self._log("ERROR: Packed import failed -> {}".format(exc))
            self._finish_progress("Packed import failed", state="error")

        self._refresh_mesh_status_only()

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Separate Utilities window
# ---------------------------------------------------------------------------

class SkinCopyToolWindow(BaseToolDialog):
    """Side-by-side sources and targets UI supporting 1-to-Many and N-to-N transfers."""

    OBJECT_NAME = "ScarToolsSkinCopyWindow"
    TOOL_ID = "skin"
    METHODS = (
        ("Vertex Index (Fast API)", "vertexIndex"),
        ("Closest Point", "closestPoint"),
        ("UV Space", "uvSpace"),
    )

    def __init__(self, operation="weights", parent=None, log_source=None):
        super(SkinCopyToolWindow, self).__init__(
            parent if parent is not None else maya_main_window()
        )
        self.operation = "cluster" if operation == "cluster" else "weights"
        self._log_source = log_source or QtWidgets.QPlainTextEdit()
        self._log_dialog = None
        self._progress_popup = None
        self._source = None
        self._sources = []
        self._targets = []
        self.setObjectName(self.OBJECT_NAME + self.operation.title())
        title = "Copy SkinCluster" if self.operation == "cluster" else "Copy Skin Weights"
        self.setWindowTitle(title)
        apply_window_icon(self)
        configure_window(self, (820, 520), (880, 580))
        self.setModal(False)
        self._build_ui()
        self._connect()
        apply_theme(self)
        self._update_state()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)
        if self.operation == "cluster":
            title = "COPY SKINCLUSTER"
            subtitle = "Create matching binding, settings, and weights"
            action = "COPY SKINCLUSTER"
        else:
            title = "COPY SKIN WEIGHTS"
            subtitle = "Transfer weights to existing skinClusters"
            action = "COPY SKIN WEIGHTS"
        header, _ = create_brand_header(title, subtitle, parent=self)
        root.addWidget(header)

        # Side-by-side Sources & Targets Layout
        tables_layout = QtWidgets.QHBoxLayout()
        tables_layout.setSpacing(GROUP_SPACING)

        # Sources Panel (Left)
        source_panel, source_layout, _ = create_section_panel(
            "Sources", accent="copy", parent=self
        )
        source_top = QtWidgets.QHBoxLayout()
        self.source_count = QtWidgets.QLabel("0 sources loaded")
        self.source_count.setObjectName("CountBadge")
        source_top.addWidget(self.source_count)
        source_top.addStretch(1)
        self.load_sources_button = create_button("Load Selected")
        self.clear_sources_button = create_button("Clear")
        source_top.addWidget(self.load_sources_button)
        source_top.addWidget(self.clear_sources_button)
        source_layout.addLayout(source_top)

        self.source_table = create_data_table(
            ["Mesh", "SkinCluster", "Status"],
            stretch_columns=(0, 1),
            fixed_columns={2: TABLE_STATUS_WIDTH},
            parent=self,
        )
        self.source_table.setMinimumHeight(170)
        source_layout.addWidget(self.source_table)
        tables_layout.addWidget(source_panel, 1)

        # Targets Panel (Right)
        target_panel, target_layout, _ = create_section_panel(
            "Targets", accent="data", parent=self
        )
        target_top = QtWidgets.QHBoxLayout()
        self.target_count = QtWidgets.QLabel("0 targets loaded")
        self.target_count.setObjectName("CountBadge")
        target_top.addWidget(self.target_count)
        target_top.addStretch(1)
        self.load_targets_button = create_button("Load Selected")
        self.clear_targets_button = create_button("Clear")
        target_top.addWidget(self.load_targets_button)
        target_top.addWidget(self.clear_targets_button)
        target_layout.addLayout(target_top)

        self.target_table = create_data_table(
            ["Mesh", "SkinCluster", "Status"],
            stretch_columns=(0, 1),
            fixed_columns={2: TABLE_STATUS_WIDTH},
            parent=self,
        )
        self.target_table.setMinimumHeight(170)
        target_layout.addWidget(self.target_table)
        tables_layout.addWidget(target_panel, 1)

        root.addLayout(tables_layout, 1)

        # Transfer Settings
        settings_panel, settings_layout, _ = create_section_panel(
            "Transfer Settings", accent="copy", layout_kind="grid", parent=self
        )
        settings_layout.setColumnStretch(1, 1)
        method_label = QtWidgets.QLabel("Method")
        method_label.setMinimumWidth(FORM_LABEL_WIDTH)
        self.method_combo = QtWidgets.QComboBox()
        self.method_combo.addItems([label for label, _key in self.METHODS])
        self.method_combo.setCurrentIndex(0 if self.operation == "cluster" else 1)
        configure_field(self.method_combo)
        self.method_help = QtWidgets.QLabel()
        self.method_help.setObjectName("Hint")
        self.method_help.setWordWrap(True)
        settings_layout.addWidget(method_label, 0, 0)
        settings_layout.addWidget(self.method_combo, 0, 1)
        settings_layout.addWidget(self.method_help, 1, 1)
        root.addWidget(settings_panel)

        (
            footer, self.warning_label, self.copy_button, self.status_dot,
            self.status_label, self.view_log_button, _
        ) = create_action_footer(action, parent=self)
        root.addWidget(footer)

    def _connect(self):
        self.load_sources_button.clicked.connect(self._load_sources)
        self.clear_sources_button.clicked.connect(self._clear_sources)
        self.load_targets_button.clicked.connect(self._load_targets)
        self.clear_targets_button.clicked.connect(self._clear_targets)
        self.method_combo.currentIndexChanged.connect(self._update_state)
        self.copy_button.clicked.connect(self._run_copy)
        self.view_log_button.clicked.connect(self._show_log)

    def _load_sources(self):
        meshes = selected_meshes()
        self._sources = []
        seen = set()
        for mesh in meshes:
            if mesh in seen:
                continue
            seen.add(mesh)
            self._sources.append(mesh)
        self._refresh_sources()
        self._log("SOURCES: {} mesh(es) loaded.".format(len(self._sources)))

    def _clear_sources(self):
        self._sources = []
        self._refresh_sources()

    def _load_targets(self):
        meshes = selected_meshes()
        self._targets = []
        seen = set()
        for mesh in meshes:
            if mesh in seen:
                continue
            seen.add(mesh)
            self._targets.append(mesh)
        self._refresh_targets()
        self._log("TARGETS: {} mesh(es) loaded.".format(len(self._targets)))

    def _clear_targets(self):
        self._targets = []
        self._refresh_targets()

    def _prune_dead_nodes(self):
        """Discard loaded Maya nodes that were renamed or deleted."""
        if self._source and not cmds.objExists(self._source):
            self._source = None
        live_sources = [mesh for mesh in self._sources if cmds.objExists(mesh)]
        if len(live_sources) != len(self._sources):
            self._log("WARNING: Removed missing source mesh entries.")
            self._sources = live_sources
        live_targets = [mesh for mesh in self._targets if cmds.objExists(mesh)]
        if len(live_targets) != len(self._targets):
            self._log("WARNING: Removed missing target mesh entries.")
            self._targets = live_targets

    def _refresh_sources(self):
        self._prune_dead_nodes()
        self._source = self._sources[0] if len(self._sources) == 1 else None
        self.source_table.setRowCount(0)
        for mesh in self._sources:
            row = self.source_table.rowCount()
            self.source_table.insertRow(row)
            skin = _skin_cluster(mesh)
            valid = bool(skin)
            status = "READY" if valid else "NO SKIN"
            mesh_item = QtWidgets.QTableWidgetItem(_short_name(mesh))
            mesh_item.setData(QtCore.Qt.UserRole, mesh)
            mesh_item.setToolTip(mesh)
            skin_item = QtWidgets.QTableWidgetItem(_short_name(skin) if skin else "—")
            status_item = QtWidgets.QTableWidgetItem(status)
            status_item.setTextAlignment(QtCore.Qt.AlignCenter)
            status_item.setForeground(
                QtGui.QColor("#72d6aa") if valid else QtGui.QColor("#f07d7d")
            )
            self.source_table.setItem(row, 0, mesh_item)
            self.source_table.setItem(row, 1, skin_item)
            self.source_table.setItem(row, 2, status_item)
        count = len(self._sources)
        self.source_count.setText(
            "1 source loaded" if count == 1 else "{} sources loaded".format(count)
        )
        self._update_state()

    def _refresh_targets(self):
        self._prune_dead_nodes()
        self.target_table.setRowCount(0)
        for mesh in self._targets:
            row = self.target_table.rowCount()
            self.target_table.insertRow(row)
            skin = _skin_cluster(mesh)
            valid = bool(skin) if self.operation == "weights" else not bool(skin)
            status = "READY" if valid else (
                "NO SKIN" if self.operation == "weights" else "SKINNED"
            )
            mesh_item = QtWidgets.QTableWidgetItem(_short_name(mesh))
            mesh_item.setData(QtCore.Qt.UserRole, mesh)
            mesh_item.setToolTip(mesh)
            skin_item = QtWidgets.QTableWidgetItem(_short_name(skin) if skin else "—")
            status_item = QtWidgets.QTableWidgetItem(status)
            status_item.setTextAlignment(QtCore.Qt.AlignCenter)
            status_item.setForeground(
                QtGui.QColor("#72d6aa") if valid else QtGui.QColor("#f07d7d")
            )
            self.target_table.setItem(row, 0, mesh_item)
            self.target_table.setItem(row, 1, skin_item)
            self.target_table.setItem(row, 2, status_item)
        count = len(self._targets)
        self.target_count.setText(
            "1 target loaded" if count == 1 else "{} targets loaded".format(count)
        )
        self._update_state()

    def _method_key(self):
        return self.METHODS[self.method_combo.currentIndex()][1]

    def _update_state(self, *_):
        self._prune_dead_nodes()
        method = self._method_key()
        helps = {
            "vertexIndex": "Fast Maya API 2.0 transfer; source and targets must have identical vertex order.",
            "closestPoint": "Transfers by closest surface position; suitable for similar meshes.",
            "uvSpace": "Transfers through each mesh's current UV set.",
        }
        self.method_help.setText(helps[method])

        src_count = len(self._sources)
        tgt_count = len(self._targets)

        valid_sources = bool(self._sources)
        for mesh in self._sources:
            if not _skin_cluster(mesh):
                valid_sources = False
                break

        valid_targets = bool(self._targets)
        for mesh in self._targets:
            skin = _skin_cluster(mesh)
            if (self.operation == "weights" and not skin) or (
                self.operation == "cluster" and skin
            ):
                valid_targets = False
                break

        is_one_to_many = (src_count == 1 and tgt_count >= 1)
        is_n_to_n = (src_count > 1 and src_count == tgt_count)

        enabled = bool(valid_sources and valid_targets and (is_one_to_many or is_n_to_n))
        self.copy_button.setEnabled(enabled)

        if not self._sources:
            warning = "Load source mesh(es) on the left."
        elif not valid_sources:
            warning = "All source meshes must have a skinCluster."
        elif not self._targets:
            warning = "Load target mesh(es) on the right."
        elif not valid_targets:
            warning = (
                "All target meshes must already be skinned."
                if self.operation == "weights"
                else "All target meshes must be unskinned."
            )
        elif src_count > 1 and src_count != tgt_count:
            warning = "Source count ({}) and Target count ({}) must match for N-to-N transfer (or load 1 source for 1-to-Many).".format(
                src_count, tgt_count
            )
        elif is_one_to_many:
            warning = "Ready to copy from '{}' to {} target(s) (1-to-Many) • Maya API 2.0".format(
                _short_name(self._sources[0]), tgt_count
            )
        else:
            warning = "Ready to copy {} source/target pair(s) (N-to-N) • Maya API 2.0".format(
                src_count
            )

        self.warning_label.setText(warning)
        self.warning_label.setProperty("state", "neutral" if enabled else "warning")
        repolish(self.warning_label)

    def _run_copy(self):
        self._prune_dead_nodes()
        self._update_state()
        if not self.copy_button.isEnabled():
            return
        operation = copy_skin_cluster if self.operation == "cluster" else copy_skin_weights
        label = "Copy SkinCluster" if self.operation == "cluster" else "Copy Skin Weights"
        self.copy_button.setEnabled(False)

        source_payload = self._sources[0] if len(self._sources) == 1 else list(self._sources)
        target_count = len(self._targets)
        is_one_to_many = len(self._sources) == 1

        self._progress_popup = OperationProgressPopup(
            title="Skin Tools - Processing", parent=self, unit="meshes"
        )
        self._progress_popup.start(label, target_count)
        self._set_status("Copying skin...", "running")
        try:
            def progress(value, message=None):
                self._progress_popup.update_progress(value, message=message)
                QtWidgets.QApplication.processEvents()

            result = operation(
                source_payload,
                list(self._targets),
                method=self._method_key(),
                log=self._log,
                progress=progress,
            )
            self._progress_popup.finish(
                "Complete: {} target(s)".format(len(result["targets"])), "success"
            )
            self._progress_popup = None
            mode_text = "1-to-Many" if is_one_to_many else "N-to-N"
            self._set_status("Copy completed ({}) — Ctrl+Z to undo".format(mode_text), "success")
            self._log("COMPLETE: {} target(s) transferred ({}); one Ctrl+Z undo step.".format(
                len(result["targets"]), mode_text
            ))
            self._refresh_sources()
            self._refresh_targets()
        except Exception as exc:
            if self._progress_popup:
                self._progress_popup.finish("Copy failed — see log", "error")
                self._progress_popup = None
            self._log("ERROR: {}".format(exc))
            self._set_status("Copy failed — view log", "error")
            QtWidgets.QMessageBox.critical(self, label, str(exc))
        finally:
            self._update_state()

    def _set_status(self, text, state="idle"):
        self.status_label.setText(str(text))
        self.status_label.setProperty("state", state)
        self.status_dot.setProperty("state", state)
        repolish(self.status_label)
        repolish(self.status_dot)

    def _log(self, message):
        self._log_source.appendPlainText("[SkinCopy] {}".format(message))
        try:
            from scartools.framework.logging import emit_log
            emit_log(message, source="Skin Tools")
        except Exception:
            pass
        QtWidgets.QApplication.processEvents()

    def _error(self, message):
        self._log("ERROR: {}".format(message))
        self._set_status("Error — view log", "error")
        QtWidgets.QMessageBox.critical(self, self.windowTitle(), message)

    def _show_log(self):
        try:
            from scartools.ui.logs import show_global_log
            show_global_log(source="Skin Tools", parent=self)
        except Exception:
            pass



class SkinMirrorToolWindow(BaseToolDialog):
    """Multi-mesh mirror settings tool window."""

    OBJECT_NAME = "ScarToolsSkinMirrorWindow"
    TOOL_ID = "skin"

    ASSOCIATIONS = (
        ("Auto (Labels -> Names -> Position)", "auto"),
        ("Name Matching (L_ <-> R_)", "names"),
        ("Joint Labels (Side / Type)", "labels"),
        ("Closest Joint Position", "positions"),
    )

    def __init__(self, parent=None, mirror_callback=None, log_source=None):
        super(SkinMirrorToolWindow, self).__init__(
            parent if parent is not None else maya_main_window()
        )
        self._mirror_callback = mirror_callback
        self._log_source = log_source or QtWidgets.QPlainTextEdit()
        self._log_dialog = None
        self._progress_popup = None
        self._meshes = []
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle("Mirror Skin Weights")
        apply_window_icon(self)
        configure_window(self, (580, 480), (640, 540))
        self.setModal(False)
        self._build_ui()
        self._connect()
        apply_theme(self)
        self._update_state()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        header, _subtitle = create_brand_header(
            "MIRROR SKIN WEIGHTS",
            "Multi-mesh directional skinCluster weight mirror",
            parent=self,
        )
        root.addWidget(header)

        # Meshes Panel
        mesh_panel, mesh_layout, _ = create_section_panel(
            "Meshes to Mirror", accent="mirror", parent=self
        )
        top = QtWidgets.QHBoxLayout()
        self.mesh_count = QtWidgets.QLabel("0 meshes loaded")
        self.mesh_count.setObjectName("CountBadge")
        top.addWidget(self.mesh_count)
        top.addStretch(1)
        self.load_meshes_button = create_button("Load Selected")
        self.clear_meshes_button = create_button("Clear")
        top.addWidget(self.load_meshes_button)
        top.addWidget(self.clear_meshes_button)
        mesh_layout.addLayout(top)

        self.mesh_table = create_data_table(
            ["Mesh", "SkinCluster", "Status"],
            stretch_columns=(0, 1),
            fixed_columns={2: TABLE_STATUS_WIDTH},
            parent=self,
        )
        self.mesh_table.setMinimumHeight(130)
        mesh_layout.addWidget(self.mesh_table)
        root.addWidget(mesh_panel, 1)

        # Mirror Settings Panel
        settings_group, settings_layout, _settings_title = create_section_panel(
            "Mirror Settings",
            accent="copy",
            layout_kind="grid",
            parent=self,
        )
        settings_layout.setColumnStretch(1, 1)
        settings_layout.setColumnStretch(3, 1)

        # Row 0: Axis & Direction
        axis_label = QtWidgets.QLabel("Axis")
        axis_label.setMinimumWidth(FORM_LABEL_WIDTH)
        self.axis_combo = QtWidgets.QComboBox()
        self.axis_combo.addItems(["X", "Y", "Z"])
        self.axis_combo.setCurrentText("X")
        configure_field(self.axis_combo)

        direction_label = QtWidgets.QLabel("Direction")
        direction_label.setMinimumWidth(FORM_LABEL_WIDTH)
        self.direction_combo = QtWidgets.QComboBox()
        configure_field(self.direction_combo)
        self._update_direction_labels()

        settings_layout.addWidget(axis_label, 0, 0)
        settings_layout.addWidget(self.axis_combo, 0, 1)
        settings_layout.addWidget(direction_label, 0, 2)
        settings_layout.addWidget(self.direction_combo, 0, 3)

        # Row 1: Tolerance & Influence Association
        tol_label = QtWidgets.QLabel("Tolerance")
        tol_label.setMinimumWidth(FORM_LABEL_WIDTH)
        self.tolerance_spin = QtWidgets.QDoubleSpinBox()
        self.tolerance_spin.setRange(0.00001, 1.0)
        self.tolerance_spin.setDecimals(5)
        self.tolerance_spin.setSingleStep(0.0005)
        self.tolerance_spin.setValue(0.00100)
        configure_field(self.tolerance_spin)

        assoc_label = QtWidgets.QLabel("Influences")
        assoc_label.setMinimumWidth(FORM_LABEL_WIDTH)
        self.assoc_combo = QtWidgets.QComboBox()
        for label, _key in self.ASSOCIATIONS:
            self.assoc_combo.addItem(label)
        configure_field(self.assoc_combo)

        settings_layout.addWidget(tol_label, 1, 0)
        settings_layout.addWidget(self.tolerance_spin, 1, 1)
        settings_layout.addWidget(assoc_label, 1, 2)
        settings_layout.addWidget(self.assoc_combo, 1, 3)

        root.addWidget(settings_group)

        # Footer (Consistent standard action footer)
        (
            footer,
            self.warning_label,
            self.mirror_button,
            self.status_dot,
            self.status_label,
            self.view_log_button,
            _,
        ) = create_action_footer(
            "MIRROR SKIN WEIGHTS",
            parent=self,
        )
        root.addWidget(footer)

    def _connect(self):
        self.axis_combo.currentTextChanged.connect(self._on_axis_changed)
        self.direction_combo.currentIndexChanged.connect(self._update_state)
        self.tolerance_spin.valueChanged.connect(self._update_state)
        self.assoc_combo.currentIndexChanged.connect(self._update_state)
        self.load_meshes_button.clicked.connect(self._load_meshes)
        self.clear_meshes_button.clicked.connect(self._clear_meshes)
        self.mirror_button.clicked.connect(self._run_mirror)
        self.view_log_button.clicked.connect(self._show_log)

    def _on_axis_changed(self, text):
        self._update_direction_labels()
        self._update_state()

    def _update_direction_labels(self):
        axis = self.axis_combo.currentText() or "X"
        current = self.direction_combo.currentIndex()
        self.direction_combo.blockSignals(True)
        self.direction_combo.clear()
        self.direction_combo.addItems([
            "+{} -> -{}".format(axis, axis),
            "-{} -> +{}".format(axis, axis),
        ])
        self.direction_combo.setCurrentIndex(1 if current == 1 else 0)
        self.direction_combo.blockSignals(False)

    def _load_meshes(self):
        meshes = selected_meshes()
        self._meshes = []
        seen = set()
        for mesh in meshes:
            if mesh in seen:
                continue
            seen.add(mesh)
            self._meshes.append(mesh)
        self._refresh_meshes()
        self._log("MESHES: {} mesh(es) loaded.".format(len(self._meshes)))

    def _clear_meshes(self):
        self._meshes = []
        self._refresh_meshes()

    def _prune_dead_nodes(self):
        live = [m for m in self._meshes if cmds.objExists(m)]
        if len(live) != len(self._meshes):
            self._log("WARNING: Removed missing mesh entries.")
            self._meshes = live

    def _refresh_meshes(self):
        self._prune_dead_nodes()
        self.mesh_table.setRowCount(0)
        for mesh in self._meshes:
            row = self.mesh_table.rowCount()
            self.mesh_table.insertRow(row)
            skin = _skin_cluster(mesh)
            valid = bool(skin)
            status = "READY" if valid else "NO SKIN"
            mesh_item = QtWidgets.QTableWidgetItem(_short_name(mesh))
            mesh_item.setData(QtCore.Qt.UserRole, mesh)
            mesh_item.setToolTip(mesh)
            skin_item = QtWidgets.QTableWidgetItem(_short_name(skin) if skin else "—")
            status_item = QtWidgets.QTableWidgetItem(status)
            status_item.setTextAlignment(QtCore.Qt.AlignCenter)
            status_item.setForeground(
                QtGui.QColor("#72d6aa") if valid else QtGui.QColor("#f07d7d")
            )
            self.mesh_table.setItem(row, 0, mesh_item)
            self.mesh_table.setItem(row, 1, skin_item)
            self.mesh_table.setItem(row, 2, status_item)
        count = len(self._meshes)
        self.mesh_count.setText(
            "1 mesh loaded" if count == 1 else "{} meshes loaded".format(count)
        )
        self._update_state()

    def _has_selected_vertices(self, target_meshes):
        return any(bool(_selected_vertex_indices(m)) for m in target_meshes)

    def _update_state(self, *_):
        self._prune_dead_nodes()
        target_meshes = self._meshes if self._meshes else selected_meshes()
        valid = bool(target_meshes)
        for mesh in target_meshes:
            if not _skin_cluster(mesh):
                valid = False
                break

        self.mirror_button.setEnabled(valid)
        axis = self.axis_combo.currentText() or "X"
        direction = self.direction_combo.currentText() or "+X -> -X"

        if not target_meshes:
            warning = "Load skinned meshes or select meshes in the viewport."
        elif not valid:
            warning = "All target meshes must have an existing skinCluster."
        else:
            is_vtx = self._has_selected_vertices(target_meshes)
            vtx_str = " (selected vertices only)" if is_vtx else ""
            warning = "Ready to mirror {} mesh(es) across {}{}".format(
                len(target_meshes), direction, vtx_str
            )

        self.warning_label.setText(warning)
        self.warning_label.setProperty("state", "neutral" if valid else "warning")
        repolish(self.warning_label)

    def _run_mirror(self):
        self._prune_dead_nodes()
        target_meshes = list(self._meshes) if self._meshes else selected_meshes()
        if not target_meshes:
            self._error("Load skinned meshes or select meshes in the viewport.")
            return

        axis = self.axis_combo.currentText() or "X"
        positive_to_negative = self.direction_combo.currentIndex() == 0
        tolerance = self.tolerance_spin.value()
        selected_verts = self._has_selected_vertices(target_meshes)
        association = self.ASSOCIATIONS[self.assoc_combo.currentIndex()][1]

        self.mirror_button.setEnabled(False)
        self._progress_popup = OperationProgressPopup(
            title="Mirror Skin Weights - Processing", parent=self, unit="meshes"
        )
        self._progress_popup.start("Mirroring Skin Weights", len(target_meshes))
        self._set_status("Mirroring skin weights...", "running")
        try:
            def progress(value, message=None):
                self._progress_popup.update_progress(value, message=message)
                QtWidgets.QApplication.processEvents()

            result = mirror_skin_weights_from_selected(
                axis=axis,
                positive_to_negative=positive_to_negative,
                tolerance=tolerance,
                selected_vertices_only=selected_verts,
                association=association,
                meshes=target_meshes,
                log=self._log,
                progress=progress,
            )
            mirrored_count = len(result.get("meshes", []))
            self._progress_popup.finish(
                "Complete: {} mesh(es)".format(mirrored_count), "success"
            )
            self._progress_popup = None
            mode_text = "selected vertices only" if selected_verts else "full mesh"
            self._set_status("Mirror completed ({}) — Ctrl+Z to undo".format(mode_text), "success")
            self._log("COMPLETE: {} mesh(es) mirrored ({}); one Ctrl+Z undo step.".format(
                mirrored_count, mode_text
            ))
            self._refresh_meshes()
        except Exception as exc:
            if self._progress_popup:
                self._progress_popup.finish("Mirror failed — see log", "error")
                self._progress_popup = None
            self._log("ERROR: {}".format(exc))
            self._set_status("Mirror failed — view log", "error")
            QtWidgets.QMessageBox.critical(self, "Mirror Skin Weights", str(exc))
        finally:
            self.mirror_button.setEnabled(True)
            self._update_state()

    def _set_status(self, text, state="idle"):
        self.status_label.setText(str(text))
        self.status_label.setProperty("state", state)
        self.status_dot.setProperty("state", state)
        repolish(self.status_label)
        repolish(self.status_dot)

    def _log(self, message):
        if self._log_source is not None:
            self._log_source.appendPlainText("[SkinMirror] {}".format(message))
        try:
            from scartools.framework.logging import emit_log
            emit_log(message, source="Skin Tools")
        except Exception:
            pass
        QtWidgets.QApplication.processEvents()

    def _error(self, message):
        self._log("ERROR: {}".format(message))
        self._set_status("Error — view log", "error")
        QtWidgets.QMessageBox.critical(self, self.windowTitle(), message)

    def _show_log(self):
        try:
            from scartools.ui.logs import show_global_log
            show_global_log(source="Skin Tools", parent=self)
        except Exception:
            pass


class SkinUtilitiesWindow(BaseToolDialog):
    """Prioritized dashboard of modular skinCluster utilities."""

    OBJECT_NAME = "ScarToolsSkinUtilitiesPage"
    TOOL_ID = "skin"

    def __init__(self, parent=None, embedded=False):
        super(SkinUtilitiesWindow, self).__init__(
            parent if parent is not None else maya_main_window()
        )

        self._embedded = embedded
        if embedded:
            self.setWindowFlags(QtCore.Qt.Widget)

        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle("Skin Tools - Utilities")
        apply_window_icon(self)
        if embedded:
            configure_window(self, (0, 0))
        else:
            configure_window(self, (700, 590), (820, 640))
        self._progress_popup = None

        self._build_ui()
        self._connect()
        apply_theme(self)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root, embedded=self._embedded)

        # A standalone utilities window keeps its own header. The tabbed host
        # supplies the shared Skin Tools header when embedded.
        if not self._embedded:
            header, _subtitle = create_brand_header(
                "SKIN UTILITIES",
                "Standalone skinCluster utilities",
                parent=self,
            )
            root.addWidget(header)

        cards = QtWidgets.QGridLayout()
        cards.setHorizontalSpacing(CARD_SPACING)
        cards.setVerticalSpacing(CARD_SPACING)

        copy_weights_card, self.copy_weights_button = create_action_card(
            title="Copy Skin Weights",
            description=(
                "Transfer weights from one skinned source to existing target "
                "skinClusters."
            ),
            action_text="OPEN COPY WEIGHTS",
            icon_name="utility_copy_weights.png",
            accent="copy",
            parent=self,
        )
        self.copy_weights_button.setToolTip(
            "Copy weights without changing target skinCluster bindings.\n\n"
            "Explicitly load one source and one or more targets.\n"
            "Supports Vertex Index, Closest Point, and UV Space."
        )

        copy_cluster_card, self.copy_cluster_button = create_action_card(
            title="Copy SkinCluster",
            description=(
                "Create matching target skinClusters with the source "
                "influences, settings, and weights."
            ),
            action_text="OPEN COPY SKINCLUSTER",
            icon_name="utility_copy_cluster.png",
            accent="cluster",
            parent=self,
        )
        self.copy_cluster_button.setToolTip(
            "Duplicate a complete source binding onto unskinned targets.\n\n"
            "Existing target skinClusters are never overwritten.\n"
            "The full operation is one Maya Ctrl+Z undo step."
        )

        cleanup_card, self.remove_button = create_action_card(
            title="Remove Unused Influences",
            description=(
                "Remove zero-weight joints from selected skinClusters. "
                "Existing vertex weights remain unchanged."
            ),
            action_text="REMOVE UNUSED INFLUENCES",
            icon_name="utility_cleanup_skin.png",
            accent="cleanup",
            parent=self,
        )
        self.remove_button.setToolTip(
            "Remove unused influences from the currently selected skinned mesh(es).\n\n"
            "Uses the live Maya viewport / Outliner selection.\n"
            "Removes only influences with no effective vertex weight.\n"
            "Existing skin weights are preserved.\n"
            "Multiple selected meshes are supported.\n"
            "The complete cleanup can be undone in one step."
        )

        mirror_card, self.mirror_tool_button = create_action_card(
            title="Mirror Skin Weights",
            description=(
                "Mirror selected skinClusters across X, Y, or Z from a chosen "
                "source side, with one Ctrl+Z undo step."
            ),
            action_text="OPEN MIRROR TOOL",
            icon_name="utility_mirror_skin.png",
            accent="mirror",
            parent=self,
        )
        self.mirror_tool_button.setToolTip(
            "Open the Maya API 2.0 skin mirror tool.\n\n"
            "The mirror window contains Axis and Direction settings.\n"
            "It works on all skinned meshes selected in the Maya viewport / Outliner.\n"
            "The complete multi-mesh mirror is one Maya Ctrl+Z undo step."
        )
        cards.addWidget(copy_weights_card, 0, 0)
        cards.addWidget(copy_cluster_card, 0, 1)
        cards.addWidget(mirror_card, 1, 0)
        cards.addWidget(cleanup_card, 1, 1)
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)
        root.addLayout(cards)
        root.addStretch(1)

        # Compact idle status. Processing details appear in a popup.
        status_bar, self.status_dot, self.status_label, self.view_log_button, _ = (
            create_status_bar(parent=self)
        )
        root.addWidget(status_bar)

        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)

    def _connect(self):
        self.copy_weights_button.clicked.connect(self._show_copy_weights_tool)
        self.copy_cluster_button.clicked.connect(self._show_copy_cluster_tool)
        self.remove_button.clicked.connect(self._execute_remove_unused)
        self.mirror_tool_button.clicked.connect(self._show_mirror_tool)
        self.view_log_button.clicked.connect(self._show_log_dialog)

    def _show_copy_weights_tool(self):
        self._show_copy_tool("weights")

    def _show_copy_cluster_tool(self):
        self._show_copy_tool("cluster")

    def _show_copy_tool(self, operation):
        attribute = "_copy_{}_dialog".format(operation)
        dialog = getattr(self, attribute, None)
        # Maya/PySide can destroy C++ Qt objects while the Python reference
        # still exists. Recreate stale dialogs instead of calling methods on
        # a deleted QObject.
        try:
            alive = dialog is not None and _qt_is_valid(dialog)
        except Exception:
            alive = dialog is not None
        if not alive:
            dialog = SkinCopyToolWindow(
                operation=operation,
                parent=maya_main_window(),
                log_source=self.log_box,
            )
            setattr(self, attribute, dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _show_mirror_tool(self):
        dialog = getattr(self, "_mirror_tool_dialog", None)
        try:
            alive = dialog is not None and _qt_is_valid(dialog)
        except Exception:
            alive = dialog is not None
        if not alive:
            dialog = SkinMirrorToolWindow(
                parent=maya_main_window(),
                mirror_callback=self._execute_mirror_skin,
                log_source=self.log_box,
            )
            self._mirror_tool_dialog = dialog

        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _execute_remove_unused(self):
        # Always use Maya's live viewport/Outliner selection at click time.
        meshes = selected_meshes()
        if not meshes:
            self._error(
                "Remove Unused Influences",
                "Select one or more polygon meshes in the Maya viewport or "
                "Outliner, then run Remove Unused Influences."
            )
            return

        skinned = [mesh for mesh in meshes if _skin_cluster(mesh)]
        skipped = [mesh for mesh in meshes if mesh not in skinned]

        if not skinned:
            self._error(
                "Remove Unused Influences",
                "None of the selected meshes has a skinCluster."
            )
            return

        for mesh in skipped:
            self._log("SKIP: No skinCluster on {}".format(_short_name(mesh)))

        self._begin_progress("Removing Unused Influences", len(skinned))
        self._log(
            "Starting unused-influence cleanup: {} mesh(es).".format(
                len(skinned)
            )
        )

        old_selection = cmds.ls(sl=True, long=True) or []
        removed_total = 0
        succeeded = 0
        errors = 0

        cmds.undoInfo(
            openChunk=True,
            chunkName="ScarTools_RemoveUnusedInfluences"
        )

        try:
            total = len(skinned)
            for index, mesh in enumerate(skinned):
                self._set_progress_mesh(_short_name(mesh))
                self._progress(
                    int((index / float(total)) * 100),
                    "Checking {}...".format(_short_name(mesh)),
                    current=index,
                    total=total
                )

                try:
                    skin = _skin_cluster(mesh)
                    before_count = len(_skin_influence_paths(skin))
                    start = time.perf_counter()
                    removed = remove_unused_influences(
                        node=mesh,
                        threshold=EPSILON,
                        log=self._log
                    )
                    elapsed = time.perf_counter() - start
                    after_skin = _skin_cluster(mesh)
                    after_count = (
                        len(_skin_influence_paths(after_skin))
                        if after_skin else 0
                    )

                    removed_total += len(removed)
                    succeeded += 1
                    self._log(
                        "DONE: {} | {} -> {} influences | removed {} | {:.3f}s".format(
                            _short_name(mesh),
                            before_count,
                            after_count,
                            len(removed),
                            elapsed
                        )
                    )

                    if removed:
                        self._log(
                            "  Removed: {}".format(
                                ", ".join(_short_name(x) for x in removed)
                            )
                        )
                except Exception as exc:
                    errors += 1
                    self._log(
                        "ERROR: {} -> {}".format(_short_name(mesh), exc)
                    )

                self._progress(
                    int(((index + 1) / float(total)) * 100),
                    "Cleanup — {} completed".format(_short_name(mesh)),
                    current=index + 1,
                    total=total
                )
        finally:
            cmds.undoInfo(closeChunk=True)
            if old_selection:
                try:
                    cmds.select(old_selection, replace=True)
                except Exception:
                    pass

        if errors:
            self._finish_progress(
                "Cleanup finished with errors — see log", state="error"
            )
        else:
            self._finish_progress(
                "Cleanup complete: {} influence(s) removed".format(removed_total),
                state="success"
            )

        self._log(
            "Cleanup finished. {} influence(s) removed from {} mesh(es); "
            "{} error(s).".format(removed_total, succeeded, errors)
        )

    def _execute_health_check(self):
        meshes = selected_meshes()
        if not meshes:
            self._error(
                "Skin Health Inspector",
                "Select one or more skinned polygon meshes in the Maya viewport or Outliner."
            )
            return

        skinned = [mesh for mesh in meshes if _skin_cluster(mesh)]
        if not skinned:
            self._error(
                "Skin Health Inspector",
                "None of the selected meshes has a skinCluster."
            )
            return

        self._begin_progress("Inspecting Skin Health", len(skinned))
        self.log_box.clear()
        self.log_box.appendPlainText("=" * 72)
        self.log_box.appendPlainText("INFO: SKIN TOOLS — SKIN HEALTH QA INSPECTION")
        self.log_box.appendPlainText("INFO: Inspecting {} skinned mesh(es)".format(len(skinned)))
        self.log_box.appendPlainText("=" * 72)

        reports = inspect_skin_health(skinned)
        total_unweighted = 0
        total_unnormalized = 0
        total_stray = 0
        total_nan = 0
        all_issue_components = []

        for mesh, data in reports.items():
            unw = len(data["unweighted"])
            unnorm = len(data["unnormalized"])
            stray = len(data["stray"])
            nan_cnt = len(data["nan_inf"])
            total_unweighted += unw
            total_unnormalized += unnorm
            total_stray += stray
            total_nan += nan_cnt

            if data["healthy"]:
                self._log(
                    "SUCCESS: ✓ [{}] {} ({} verts / {} joints) — 100% HEALTHY".format(
                        _short_name(mesh), _skin_cluster(mesh), data["vertex_count"], data["influence_count"]
                    )
                )
            else:
                self._log(
                    "WARNING: ⚠️ [{}] {} ({} verts / {} joints) — ISSUES DETECTED:".format(
                        _short_name(mesh), _skin_cluster(mesh), data["vertex_count"], data["influence_count"]
                    )
                )
                if unw > 0:
                    self._log("WARNING:   • Unweighted Vertices (0.0 weight): {}".format(unw))
                if unnorm > 0:
                    self._log("WARNING:   • Unnormalized Vertices (sum != 1.0): {}".format(unnorm))
                if stray > 0:
                    self._log("WARNING:   • Stray / Tiny Weight Vertices (< 1e-4): {}".format(stray))
                if nan_cnt > 0:
                    self._log("ERROR:   • Corrupted NaN / Infinite Weight Vertices: {}".format(nan_cnt))

                shape = _mesh_shape(mesh)
                for vid in data["unweighted"] + [x[0] for x in data["unnormalized"]] + data["nan_inf"]:
                    all_issue_components.append("{}.vtx[{}]".format(shape, vid))

        self._log("\n" + "=" * 72)
        if all_issue_components:
            try:
                cmds.select(all_issue_components, replace=True)
                self._log("INFO: Selected {} problematic vertex/vertices in Maya viewport.".format(len(all_issue_components)))
            except Exception:
                pass
            summary = "WARNING: Summary: Found {} unweighted, {} unnormalized, {} stray, {} NaN/Inf vertices.".format(
                total_unweighted, total_unnormalized, total_stray, total_nan
            )
            self._log(summary)
            self._finish_progress("Health check found issues — see log and viewport selection", state="warning")
            self._set_status("Issues found — vertices selected in viewport", state="warning")
        else:
            self._log("SUCCESS: ✓ Summary: All {} selected skinClusters are 100% healthy!".format(len(skinned)))
            self._finish_progress("All selected skinClusters are 100% healthy!", state="success")
            self._set_status("All selected skinClusters are 100% healthy", state="success")
        self._log("=" * 72 + "\n")


    def _execute_mirror_skin(
        self,
        axis="X",
        positive_to_negative=True,
        tolerance=1e-4,
        selected_vertices_only=False,
        association="auto",
        meshes=None,
    ):
        # Always use Maya's live viewport/Outliner selection if meshes not provided
        if meshes is not None:
            target_list = list(meshes) if isinstance(meshes, (list, tuple, set)) else [meshes]
            meshes = [_mesh_transform(m) for m in target_list if m]
        else:
            meshes = selected_meshes()
        if not meshes:
            self._error(
                "Mirror Skin Weights",
                "Select one or more polygon meshes in the Maya viewport or "
                "Outliner, then run Mirror Selected Skin."
            )
            return

        skinned = [mesh for mesh in meshes if _skin_cluster(mesh)]
        skipped = [mesh for mesh in meshes if mesh not in skinned]

        if not skinned:
            self._error(
                "Mirror Skin Weights",
                "None of the selected meshes has a skinCluster."
            )
            return

        for mesh in skipped:
            self._log("SKIP: No skinCluster on {}".format(_short_name(mesh)))

        axis = str(axis).upper()
        direction = (
            "+{} -> -{}".format(axis, axis)
            if positive_to_negative
            else "-{} -> +{}".format(axis, axis)
        )

        self._begin_progress("Mirroring Skin Weights", len(skinned))
        self._log(
            "Starting API skin mirror: {} mesh(es) | axis {} | {} | "
            "one Ctrl+Z undo step.".format(len(skinned), axis, direction)
        )

        old_selection = cmds.ls(sl=True, long=True) or []
        changes = []
        errors = 0

        try:
            # Load and validate the Maya undo bridge before spending time
            # preparing weights for every selected mesh.
            try:
                _ensure_api_undo_command()
            except Exception as exc:
                errors = len(skinned)
                self._log("ERROR: Mirror undo bridge failed -> {}".format(exc))
                self._finish_progress(
                    "Mirror could not start — see log", state="error"
                )
                return

            total = len(skinned)
            for index, mesh in enumerate(skinned):
                self._set_progress_mesh(_short_name(mesh))
                self._progress(
                    int((index / float(total)) * 85),
                    "Preparing {}...".format(_short_name(mesh)),
                    current=index,
                    total=total
                )

                try:
                    change = _prepare_mirror_skin_change(
                        node=mesh,
                        axis=axis,
                        positive_to_negative=positive_to_negative,
                        normalize=True,
                        tolerance=tolerance,
                        selected_vertices_only=selected_vertices_only,
                        association=association,
                        log=self._log
                    )
                    changes.append(change)
                    self._log(
                        "PREPARED: {} | {} target verts | exact={} fallback={} | {:.3f}s".format(
                            _short_name(mesh),
                            len(change["target_ids"]),
                            change["exact_count"],
                            change["fallback_count"],
                            change["prepare_seconds"]
                        )
                    )
                except Exception as exc:
                    errors += 1
                    self._log(
                        "ERROR: {} -> {}".format(_short_name(mesh), exc)
                    )

                self._progress(
                    int(((index + 1) / float(total)) * 85),
                    "Prepared {}".format(_short_name(mesh)),
                    current=index + 1,
                    total=total
                )

            if changes:
                self._set_progress_mesh("Applying mirrored weights...")
                self._progress(
                    90,
                    "Applying API mirror as one Maya undo operation...",
                    current=len(changes),
                    total=len(changes)
                )
                apply_started = time.perf_counter()
                try:
                    _commit_mirror_skin_changes(changes)
                    apply_elapsed = time.perf_counter() - apply_started
                    self._log(
                        "APPLIED: {} mesh(es) in {:.3f}s | Ctrl+Z undo ready.".format(
                            len(changes), apply_elapsed
                        )
                    )
                except Exception as exc:
                    errors += len(changes)
                    changes = []
                    self._log("ERROR: Mirror apply failed -> {}".format(exc))

                self._progress(
                    100,
                    "Mirror complete.",
                    current=len(changes),
                    total=len(changes)
                )
        finally:
            if old_selection:
                try:
                    cmds.select(old_selection, replace=True)
                except Exception:
                    pass

        succeeded = len(changes)
        if errors:
            self._finish_progress(
                "Mirror finished with errors — see log", state="error"
            )
        else:
            self._finish_progress(
                "Mirror complete: {} mesh(es) — Ctrl+Z to undo".format(succeeded),
                state="success"
            )

        self._log(
            "Mirror finished. {} successful; {} error(s). Ctrl+Z restores "
            "all mirrored meshes in one step.".format(succeeded, errors)
        )

    # ------------------------------------------------------------------
    # Progress / log
    # ------------------------------------------------------------------

    def _reset_progress(self):
        self._close_progress_popup()
        self._set_status("Ready", state="idle")

    def _begin_progress(self, title, total):
        self._close_progress_popup()
        self._progress_popup = OperationProgressPopup(
            title="Skin Tools - Processing",
            parent=self.window(),
            unit="meshes",
        )
        self._progress_popup.start(title, total)
        self._set_status(title, state="running")

    def _set_progress_mesh(self, mesh_name):
        if self._progress_popup:
            self._progress_popup.set_current(mesh_name)

    def _progress(self, value, message=None, current=None, total=None):
        if self._progress_popup:
            self._progress_popup.update_progress(
                value, message=message, current=current, total=total
            )
        if message:
            self._set_status(message, state="running")
        QtWidgets.QApplication.processEvents()

    def _finish_progress(self, message, state="success"):
        if self._progress_popup:
            popup = self._progress_popup
            self._progress_popup = None
            popup.finish(message, state)
        self._set_status(message, state=state)

    def _close_progress_popup(self):
        if self._progress_popup:
            try:
                self._progress_popup.close()
                self._progress_popup.deleteLater()
            except Exception:
                pass
            self._progress_popup = None

    def _set_status(self, text, state="idle"):
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_dot.setProperty("state", state)
        repolish(self.status_label)
        repolish(self.status_dot)

    def _log(self, message):
        self.log_box.appendPlainText(
            "[SkinUtilities] {}".format(message)
        )
        bar = self.log_box.verticalScrollBar()
        bar.setValue(bar.maximum())
        QtWidgets.QApplication.processEvents()

    def _error(self, title, message):
        self._close_progress_popup()
        self._log("ERROR: {}".format(message))
        self._set_status("Error — see log", state="error")
        QtWidgets.QMessageBox.critical(self, title, message)

    def _show_log_dialog(self):
        self._log_dialog = LogDialog(
            "Skin Tools - Utilities",
            self.log_box,
            parent=self,
        )
        self._log_dialog.show()
        self._log_dialog.raise_()
        self._log_dialog.activateWindow()

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Main tabbed window
# ---------------------------------------------------------------------------

class SkinToolsWindow(BaseToolDialog):
    """One Maya window with shared header and two workflow tabs."""

    OBJECT_NAME = "ScarToolsSkinToolsWindow"
    TOOL_ID = "skin"

    def __init__(self, parent=None, initial_tab=0):
        super(SkinToolsWindow, self).__init__(
            parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )

        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle("Skin Tools")
        apply_window_icon(self)
        configure_window(self, (790, 420), (850, 690))

        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # Shared header ------------------------------------------------
        # This is the shared Skin Tools header. The navigation tabs
        # intentionally sit directly below it and above the Operation panel.
        header, self.header_subtitle = create_brand_header(
            "SKIN TOOLS",
            "SkinCluster weight export and import",
            parent=self,
        )
        root.addWidget(header)

        # Top navigation -----------------------------------------------
        self.tabs = create_navigation_tabs(parent=self)

        self.export_import_page = SkinImportExportPage(
            parent=self.tabs, embedded=True
        )
        self.skin_utilities_page = SkinUtilitiesWindow(
            parent=self.tabs, embedded=True
        )

        self.tabs.addTab(self.export_import_page, "Import / Export")
        self.tabs.addTab(self.skin_utilities_page, "Utilities")
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tabs.setCurrentIndex(1 if int(initial_tab) == 1 else 0)

        root.addWidget(self.tabs, 1)
        apply_theme(self)
        self._tab_changed(self.tabs.currentIndex())

    def _tab_changed(self, index):
        if int(index) == 1:
            self.header_subtitle.setText("SkinCluster utilities")
            minimum_height = 400
            preferred_height = 430
            maximum_height = 450
        else:
            self.header_subtitle.setText("SkinCluster weight export and import")
            minimum_height = 640
            preferred_height = 690
            maximum_height = 16777215

        # Import/Export needs a large mesh table; Utilities is intentionally a
        # compact action dashboard.  Resize the host to the active workflow so
        # a short page never inherits a large empty table-sized canvas.
        # Reset both constraints first so switching from the 430 px compact
        # page to the 640 px table page cannot leave Qt with min > max.
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        self.setMinimumHeight(minimum_height)
        self.setMaximumHeight(maximum_height)
        if not getattr(self, "_scartools_rolled_up", False):
            self.resize(self.width(), preferred_height)



# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_tool_instance = None


def _show_main_window(tab_index=0):
    global _tool_instance

    from scartools.licensing import is_activated
    if not is_activated():
        try:
            from scartools.ui.license_dialog import show_license_dialog
            show_license_dialog()
        except Exception:
            pass
        return None

    try:
        if _tool_instance:
            _tool_instance.close()
            _tool_instance.deleteLater()
    except Exception:
        pass


    _tool_instance = SkinToolsWindow(
        parent=maya_main_window(), initial_tab=tab_index
    )
    _tool_instance.show()
    _tool_instance.raise_()
    _tool_instance.activateWindow()
    return _tool_instance


def show_ui():
    """Open the main window on the Export / Import tab."""
    return _show_main_window(0)


def show_skin_utilities():
    """Open the same main window directly on the Utilities tab."""
    return _show_main_window(1)


def close_all_windows():
    """Close tool windows before an update, uninstall, or plug-in unload."""
    global _tool_instance
    try:
        if _tool_instance:
            _tool_instance.close()
            _tool_instance.deleteLater()
    except Exception:
        pass
    _tool_instance = None
    from scartools.framework import close_tool_windows
    close_tool_windows("skin")
