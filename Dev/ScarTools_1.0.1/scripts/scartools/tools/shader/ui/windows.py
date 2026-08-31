"""Unified ScarTools interface for versioned shader snapshots."""

from __future__ import print_function

import os

import maya.cmds as cmds

from scartools import settings
from scartools.ui.qt import QtCore, QtGui, QtWidgets, apply_window_icon, maya_main_window
from scartools.ui.theme import apply as apply_theme
from scartools.ui import (
    BaseToolDialog,
    LogDialog,
    OperationProgressPopup,
    configure_root_layout,
    configure_window,
    create_action_footer,
    create_brand_header,
    create_button,
    create_data_table,
    create_operation_group,
    create_section_panel,
    TABLE_STATUS_WIDTH,
    repolish,
)

from ..operations import (
    ShaderToolsError,
    collect_shader_assignments,
    export_shader_snapshot,
    import_shader_package,
    inspect_shader_package,
    inspect_texture_paths,
    mesh_transforms,
    resolve_shader_snapshot,
)
from scartools.version import VERSION


class ShaderToolsWindow(BaseToolDialog):
    """Single production workflow matching the Skin Tools interaction model."""

    OBJECT_NAME = "ScarToolsShaderToolsWindow"
    TOOL_ID = "shader"

    def __init__(self, parent=None, initial_tab=0):
        super(ShaderToolsWindow, self).__init__(
            parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle("Shader Tools")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        configure_window(self, (760, 560), (850, 650))
        apply_window_icon(self)
        self._objects = []
        self._export_ready = False
        self._inspection = None
        self._json_path = ""
        self._progress_popup = None
        self._log_dialog = None
        self._build_ui()
        self._connect()
        apply_theme(self)
        self.operation_combo.setCurrentIndex(1 if int(initial_tab) == 1 else 0)
        self._mode_changed()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        header, _subtitle = create_brand_header(
            "SHADER TOOLS",
            "Maya shader network export and import",
            parent=self,
        )
        root.addWidget(header)

        operation_group, self.operation_combo, self.operation_help = (
            create_operation_group(parent=self)
        )
        root.addWidget(operation_group)

        mesh_group, mesh_layout, _mesh_title = create_section_panel(
            "Meshes", accent="texturing", parent=self
        )
        actions = QtWidgets.QHBoxLayout()
        self.count_label = QtWidgets.QLabel("0 meshes selected")
        self.count_label.setObjectName("CountBadge")
        self.refresh_button = create_button("Refresh Selection")
        self.clear_button = create_button("Clear")
        actions.addWidget(self.count_label)
        actions.addStretch(1)
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.clear_button)
        mesh_layout.addLayout(actions)

        self.mesh_table = create_data_table(
            ["Mesh", "Shaders", "Status"],
            stretch_columns=(0, 1),
            fixed_columns={2: TABLE_STATUS_WIDTH},
            extended_selection=True,
            parent=self,
        )
        mesh_layout.addWidget(self.mesh_table, 1)
        root.addWidget(mesh_group, 1)

        (
            action_footer,
            self.warning_label,
            self.action_button,
            self.status_dot,
            self.status_label,
            self.view_log_button,
            _status_layout,
        ) = create_action_footer(
            "EXPORT SHADER PACKAGE",
            parent=self,
        )
        root.addWidget(action_footer)

        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.hide()

    def _connect(self):
        self.operation_combo.currentIndexChanged.connect(self._mode_changed)
        self.refresh_button.clicked.connect(self._refresh_selection)
        self.clear_button.clicked.connect(self._clear)
        self.action_button.clicked.connect(self._run)
        self.view_log_button.clicked.connect(self._show_log)

    def _is_export(self):
        return self.operation_combo.currentIndex() == 0

    def _mode_changed(self, *_):
        self._clear()
        exporting = self._is_export()
        self.refresh_button.setVisible(exporting)
        self.operation_help.setText(
            "Select meshes, then choose a shared snapshot root."
            if exporting else
            "Choose a shared snapshot root; the latest asset version is preflighted."
        )
        self.action_button.setText(
            "EXPORT SHADER PACKAGE" if exporting else "IMPORT SHADER PACKAGE"
        )
        self.action_button.setProperty("mode", "export" if exporting else "import")
        repolish(self.action_button)
        if exporting:
            self._refresh_selection()
        else:
            self._update_action_state()

    @staticmethod
    def _item(text, color=None):
        item = QtWidgets.QTableWidgetItem(str(text))
        if color:
            item.setForeground(QtGui.QColor(color))
        return item

    def _set_rows(self, rows):
        self.mesh_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column, value in enumerate(row[:3]):
                color = row[3] if column == 2 and len(row) > 3 else None
                self.mesh_table.setItem(row_index, column, self._item(value, color))
        self.count_label.setText(
            "{} meshes selected".format(len(rows))
            if self._is_export()
            else "{} package meshes".format(len(rows))
        )

    def _refresh_selection(self):
        self._objects = mesh_transforms()
        rows = []
        assignment_counts = {}
        if self._objects:
            try:
                records, _materials = collect_shader_assignments(self._objects)
                assignment_counts = {
                    record["source_path"]: len(record["materials"])
                    for record in records
                }
            except Exception:
                assignment_counts = {}
        for transform in self._objects:
            count = assignment_counts.get(transform, 0)
            rows.append((
                transform.split("|")[-1],
                count,
                "Ready" if count else "No surface shader",
                "#72D6AA" if count else "#D6B36A",
            ))
        self._export_ready = any(assignment_counts.values())
        self._set_rows(rows)
        if self._objects and self._export_ready:
            self._set_warning(
                "{} selected mesh(es) ready for a packed shader snapshot."
                .format(len(self._objects)), "success"
            )
        elif self._objects:
            self._set_warning(
                "The selected meshes have no assigned surface shaders.", "warning"
            )
        else:
            self._set_warning(
                "No meshes loaded. Select meshes in Maya and click Refresh Selection."
            )
        self._update_action_state()

    def _clear(self):
        self._objects = []
        self._export_ready = False
        self._inspection = None
        self._json_path = ""
        self.mesh_table.setRowCount(0)
        self.count_label.setText(
            "0 meshes selected" if self._is_export() else "0 package meshes"
        )
        self._set_warning(
            "No meshes loaded. Select meshes in Maya and click Refresh Selection."
            if self._is_export() else
            "Choose Import to select and preflight the latest shader snapshot."
        )
        self._set_status("Ready", "idle")
        self._update_action_state()

    def _update_action_state(self):
        self.action_button.setEnabled(self._export_ready if self._is_export() else True)

    def _set_warning(self, text, state="neutral"):
        self.warning_label.setText(str(text))
        self.warning_label.setProperty("state", state)
        repolish(self.warning_label)

    def _set_status(self, text, state="idle"):
        self.status_label.setText(str(text))
        self.status_label.setProperty("state", state)
        self.status_dot.setProperty("state", state)
        repolish(self.status_label)
        repolish(self.status_dot)

    def _log(self, message):
        self.log_box.appendPlainText(str(message))
        try:
            from scartools.framework.logging import emit_log
            emit_log(message, source="Shader Tools")
        except Exception:
            pass
        QtWidgets.QApplication.processEvents()

    def _show_log(self):
        try:
            from scartools.ui.logs import show_global_log
            show_global_log(source="Shader Tools", parent=self)
        except Exception:
            pass


    def _choose_root(self, caption):
        start = settings.get_string("ShaderTools_LastDirectory", "")
        result = cmds.fileDialog2(
            fileMode=3,
            caption=caption,
            startingDirectory=start or os.path.expanduser("~"),
        )
        if not result:
            return None
        path = os.path.normpath(result[0])
        settings.set_string("ShaderTools_LastDirectory", path)
        return path

    def _begin_progress(self, title, count):
        self._progress_popup = OperationProgressPopup(
            title="Shader Tools - Processing", parent=self
        )
        self._progress_popup.start(title, count)
        self._set_status(title, "running")

    def _progress(self, value, message=""):
        if self._progress_popup:
            self._progress_popup.update_progress(value, message)

    def _finish_progress(self):
        if self._progress_popup:
            self._progress_popup.finish()
            self._progress_popup = None

    def _run(self):
        if self._is_export():
            self._export()
        else:
            self._import()

    def _export(self):
        root = self._choose_root("Select Shader Snapshot Root Folder")
        if not root:
            return
        self.log_box.clear()
        self.log_box.appendPlainText("=" * 72)
        self.log_box.appendPlainText("INFO: SHADER TOOLS — EXPORTING SHADER SNAPSHOT")
        self.log_box.appendPlainText("INFO: Snapshot Root: '{}'".format(root))
        self.log_box.appendPlainText("=" * 72)

        tex_check = inspect_texture_paths(self._objects)
        if not tex_check["all_valid"]:
            self._log(
                "WARNING: ⚠️ {} of {} texture file(s) missing on disk:".format(
                    tex_check["missing_count"], tex_check["total_textures"]
                )
            )
            for item in tex_check["missing_textures"]:
                self._log("WARNING:   • [{}] {}: {}".format(item["node"], item["path"], item["reason"]))
        else:
            self._log(
                "SUCCESS: ✓ Texture verification passed: {} connected texture(s) on disk.".format(
                    tex_check["total_textures"]
                )
            )

        self._begin_progress("Exporting Shader Snapshot", len(self._objects))
        try:
            result = export_shader_snapshot(
                self._objects, root, log=self._log, progress=self._progress
            )
            self._log("\n" + "=" * 72)
            self._log(
                "SUCCESS: ✓ Exported {} material(s) across {} mesh(es) to version '{}'.".format(
                    result["materials"], result["objects"], result["version"]
                )
            )
            self._log("=" * 72 + "\n")
            message = "Exported {} material(s) / {} mesh(es) to {}.".format(
                result["materials"], result["objects"], result["version"]
            )
            if not tex_check["all_valid"]:
                message += " ({} missing texture(s) - see log)".format(
                    tex_check["missing_count"]
                )
            self._set_warning(message, "warning" if not tex_check["all_valid"] else "success")
            self._set_status(
                "Export complete (with texture warnings)" if not tex_check["all_valid"] else "Export complete",
                "warning" if not tex_check["all_valid"] else "success",
            )
        except Exception as exc:
            self._log("ERROR: {}".format(exc))
            self._set_warning(str(exc), "error")

            self._set_status("Export failed", "error")
        finally:
            self._finish_progress()

    def _import(self):
        root = self._choose_root("Select Shader Snapshot Root Folder")
        if not root:
            return
        self.log_box.clear()
        self.log_box.appendPlainText("=" * 72)
        self.log_box.appendPlainText("INFO: SHADER TOOLS — IMPORT PREFLIGHT")
        self.log_box.appendPlainText("INFO: Snapshot Root: '{}'".format(root))
        self.log_box.appendPlainText("=" * 72)
        try:
            json_path, version_name = resolve_shader_snapshot(
                root, requested_directory=root
            )
            inspection = inspect_shader_package(json_path)
            if not inspection["maya_file_exists"]:
                raise ShaderToolsError(
                    "The snapshot metadata exists, but shader_package.ma is missing."
                )
        except Exception as exc:
            self._log("ERROR: {}".format(exc))
            self._set_warning(str(exc), "error")
            self._set_status("Preflight failed", "error")
            return

        rows = []
        missing = 0
        for object_data in inspection["objects"]:
            found = object_data["status"] == "found"
            if not found:
                missing += 1
            source = object_data["source"]
            material_count = 0
            for record in inspection["package"]["objects"]:
                if record["short_name"] == source:
                    material_count = len(record["materials"])
                    break
            status_text = "Matched" if found else "Missing in scene"
            rows.append((
                source,
                material_count,
                status_text,
                "#72D6AA" if found else "#E06C6C",
            ))
            if found:
                self._log("INFO:   • [{}] {} material(s) -> Matched in scene".format(source, material_count))
            else:
                self._log("WARNING: ⚠️ [{}] {} material(s) -> NOT found in active Maya scene".format(source, material_count))

        self._set_rows(rows)
        self._inspection = inspection
        self._json_path = json_path
        summary = (
            "Preflight {}: {} mesh(es), {} material(s), {} unresolved mesh(es)."
            .format(
                version_name,
                len(inspection["objects"]),
                len(inspection["materials"]),
                missing,
            )
        )
        self._log("\n" + "=" * 72)
        if missing > 0:
            self._log("WARNING: Summary: {}".format(summary))
        else:
            self._log("SUCCESS: ✓ Summary: {}".format(summary))
        self._log("=" * 72 + "\n")
        self._set_warning(summary, "warning" if missing else "success")
        answer = QtWidgets.QMessageBox.question(
            self,
            "Shader Import Preflight",
            summary + "\n\nContinue with import?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            self._set_status("Import cancelled after preflight", "idle")
            return

        self._begin_progress("Importing Shader Snapshot", len(rows))
        try:
            result = import_shader_package(
                json_path,
                reuse_existing=True,
                log=self._log,
                progress=self._progress,
                use_undo=True,
            )
            message = "Applied {} assignment(s); {} warning(s).".format(
                result["assignments"], len(result["warnings"])
            )
            for warning in result["warnings"]:
                self._log("WARNING: {}".format(warning))
            self._log("\n" + "=" * 72)
            self._log("SUCCESS: ✓ Import Complete: {}".format(message))
            self._log("=" * 72 + "\n")
            self._set_warning(
                message, "warning" if result["warnings"] else "success"
            )
            self._set_status("Import complete", "success")
        except Exception as exc:
            self._log("ERROR: {}".format(exc))
            self._set_warning(str(exc), "error")
            self._set_status("Import failed", "error")
        finally:
            self._finish_progress()



_window = None


def show_ui(initial_tab=0):
    global _window

    from scartools.licensing import is_activated
    if not is_activated():
        try:
            from scartools.ui.license_dialog import show_license_dialog
            show_license_dialog()
        except Exception:
            pass
        return None

    try:
        if _window:
            _window.close()
            _window.deleteLater()
    except Exception:
        pass

    _window = ShaderToolsWindow(
        parent=maya_main_window(), initial_tab=initial_tab
    )
    _window.show()
    _window.raise_()
    _window.activateWindow()
    return _window


def close_all_windows():
    global _window
    if _window:
        try:
            _window.close()
            _window.deleteLater()
        except Exception:
            pass
    _window = None
    from scartools.framework import close_tool_windows
    close_tool_windows("shader")
