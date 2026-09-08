# -*- coding: utf-8 -*-
"""Standalone Desktop Application for Anim Export (Background Maya Engine).

Runs outside Maya with full PySide GUI, enabling animators to drag-and-drop
scenes into a queue and export Alembic/FBX shot caches in the background.
"""

from __future__ import absolute_import, division, print_function

import os
import sys

# Ensure PySide2 or PySide6 is imported cleanly outside Maya
try:
    from PySide2 import QtCore, QtWidgets, QtGui
except ImportError:
    try:
        from PySide6 import QtCore, QtWidgets, QtGui
    except ImportError:
        raise ImportError("PySide2 or PySide6 is required to run the Standalone Anim Export UI.")

# Import ScarTools UI Design System tokens and components
from scartools.ui.tokens import (
    COLOR_BG_ROOT,
    COLOR_BG_PANEL,
    COLOR_PRIMARY_BLUE,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    COLOR_STATUS_ERROR,
    COLOR_TEXT_MUTED,
    FORM_LABEL_WIDTH,
    INLINE_SPACING,
    PRIMARY_BUTTON_WIDTH,
)
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
)
from scartools.framework import open_in_file_manager
from scartools.ui.window import BaseToolDialog

from ..standalone_runner import discover_mayapy_interpreters, BackgroundExportJob
from ..api.manifest_builder import resolve_next_version


class DropTableWidget(QtWidgets.QTableWidget):
    """Data table supporting file drag-and-drop for Maya scenes (.ma, .mb)."""

    files_dropped = QtCore.Signal(list)

    def __init__(self, parent=None):
        super(DropTableWidget, self).__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super(DropTableWidget, self).dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super(DropTableWidget, self).dragMoveEvent(event)

    def dropEvent(self, event):
        files = []
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                p = url.toLocalFile()
                if p.lower().endswith((".ma", ".mb")) and os.path.isfile(p):
                    files.append(os.path.normpath(p))
            if files:
                self.files_dropped.emit(files)
                event.acceptProposedAction()
                return
        super(DropTableWidget, self).dropEvent(event)


class AnimExportStandaloneApp(QtWidgets.QDialog):
    """
    Standalone Desktop Queue Application for Background Shot Caching.
    """

    job_progress_signal = QtCore.Signal(int, str)
    job_log_signal = QtCore.Signal(str)
    job_finished_signal = QtCore.Signal(int, bool, str)

    def __init__(self, parent=None):
        super(AnimExportStandaloneApp, self).__init__(parent)
        self.queue_items = []  # List of dicts representing queued scenes
        self.current_job = None
        self.is_processing = False

        self.setWindowTitle("ScarTools Anim Export (Standalone Background Engine)")
        configure_window(self, (720, 600), (780, 680))

        self._build_ui()
        self._connect()
        apply_theme(self)
        self._populate_interpreters()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Brand Header [UI-02]
        header, _ = create_brand_header(
            "ANIM EXPORT STANDALONE",
            "Headless background batch queue powered by mayapy.exe",
            parent=self,
        )
        root.addWidget(header)

        # 2. Configuration Section [UI-03]
        cfg_panel, cfg_layout, _ = create_section_panel("Engine Configuration", accent="pipeline", parent=self)

        # Interpreter Row
        row_py = QtWidgets.QHBoxLayout()
        row_py.setSpacing(INLINE_SPACING)
        lbl_py = QtWidgets.QLabel("Maya Engine", self)
        lbl_py.setFixedWidth(FORM_LABEL_WIDTH)
        lbl_py.setObjectName("FieldLabel")

        self.combo_mayapy = QtWidgets.QComboBox(self)
        configure_field(self.combo_mayapy, minimum_width=240)

        self.btn_browse_py = create_button("Browse mayapy...", role="secondary", parent=self)
        self.btn_browse_py.setFixedWidth(120)

        row_py.addWidget(lbl_py)
        row_py.addWidget(self.combo_mayapy, 1)
        row_py.addWidget(self.btn_browse_py)
        cfg_layout.addLayout(row_py)

        # Settings Row (Format, Version, Handles)
        row_opts = QtWidgets.QHBoxLayout()
        row_opts.setSpacing(INLINE_SPACING)

        lbl_fmt = QtWidgets.QLabel("Format", self)
        lbl_fmt.setFixedWidth(FORM_LABEL_WIDTH)
        lbl_fmt.setObjectName("FieldLabel")

        self.combo_format = QtWidgets.QComboBox(self)
        self.combo_format.addItems(["Both (Alembic + FBX)", "Alembic Only", "FBX Only"])
        configure_field(self.combo_format, minimum_width=160)

        lbl_ver = QtWidgets.QLabel("Version", self)
        lbl_ver.setObjectName("FieldLabel")

        self.combo_version = QtWidgets.QComboBox(self)
        self.combo_version.addItems(["Next (Auto-Increment)", "v001", "v002", "v003", "v004", "v005"])
        self.combo_version.setEditable(True)
        configure_field(self.combo_version, minimum_width=140)

        lbl_handles = QtWidgets.QLabel("Handles", self)
        lbl_handles.setObjectName("FieldLabel")

        self.spin_handles = QtWidgets.QSpinBox(self)
        self.spin_handles.setRange(0, 100)
        self.spin_handles.setValue(0)
        self.spin_handles.setSuffix(" frames")
        configure_field(self.spin_handles, minimum_width=90)

        row_opts.addWidget(lbl_fmt)
        row_opts.addWidget(self.combo_format)
        row_opts.addWidget(lbl_ver)
        row_opts.addWidget(self.combo_version)
        row_opts.addWidget(lbl_handles)
        row_opts.addWidget(self.spin_handles)
        row_opts.addStretch(1)
        cfg_layout.addLayout(row_opts)

        root.addWidget(cfg_panel)

        # 3. Batch Scene Queue Table [UI-03, UI-05]
        queue_panel, queue_layout, _ = create_section_panel("Shot Scene Queue (Drag & Drop .ma / .mb)", accent="data", parent=self)

        top_bar = QtWidgets.QHBoxLayout()
        self.count_badge = QtWidgets.QLabel("0 scenes in queue", self)
        self.count_badge.setObjectName("CountBadge")

        self.btn_add = create_button("+ Add Scene(s)...", role="secondary", parent=self)
        self.btn_remove = create_button("Remove Selected", role="secondary", parent=self)
        self.btn_clear = create_button("Clear All", role="secondary", parent=self)

        top_bar.addWidget(self.count_badge)
        top_bar.addStretch(1)
        top_bar.addWidget(self.btn_add)
        top_bar.addWidget(self.btn_remove)
        top_bar.addWidget(self.btn_clear)
        queue_layout.addLayout(top_bar)

        self.queue_table = DropTableWidget(self)
        self.queue_table.setColumnCount(5)
        self.queue_table.setHorizontalHeaderLabels(["Scene File", "Shot Name", "Version", "Format", "Status"])
        self.queue_table.horizontalHeader().setStretchLastSection(False)
        self.queue_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.queue_table.setColumnWidth(1, 130)
        self.queue_table.setColumnWidth(2, 85)
        self.queue_table.setColumnWidth(3, 85)
        self.queue_table.setColumnWidth(4, 110)
        self.queue_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        queue_layout.addWidget(self.queue_table, 1)

        root.addWidget(queue_panel, 1)

        # 4. Action Footer & Progress [UI-06]
        (
            action_footer,
            self.message_label,
            self.apply_button,
            self.status_dot,
            self.status_label,
            self.view_log_button,
            status_layout,
        ) = create_action_footer(
            "START BATCH EXPORT",
            message="Drag Maya animation scenes into queue or click Add Scene(s).",
            parent=self,
            include_log=True,
        )
        self.apply_button.setMinimumWidth(PRIMARY_BUTTON_WIDTH + 20)

        self.btn_cancel = create_button("Abort", role="secondary", parent=self)
        self.btn_cancel.setVisible(False)
        status_layout.insertWidget(0, self.btn_cancel)

        # Live Progress Bar
        self.progress_bar = QtWidgets.QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        root.addWidget(action_footer)

        # 5. Live Console Log (Collapsible)
        self.log_console = QtWidgets.QPlainTextEdit(self)
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(120)
        self.log_console.setVisible(False)
        self.log_console.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        root.addWidget(self.log_console)

    def _connect(self):
        self.btn_browse_py.clicked.connect(self._browse_mayapy)
        self.btn_add.clicked.connect(self._add_scenes_dialog)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self._clear_all)
        self.queue_table.files_dropped.connect(self.add_scene_files)
        self.apply_button.clicked.connect(self.start_batch_export)
        self.btn_cancel.clicked.connect(self.cancel_export)
        self.view_log_button.clicked.connect(self._toggle_console)

        # Thread-safe worker signal connections
        self.job_progress_signal.connect(self._handle_progress)
        self.job_log_signal.connect(self._handle_log)
        self.job_finished_signal.connect(self._handle_job_done)

    def _populate_interpreters(self):
        interpreters = discover_mayapy_interpreters()
        self.combo_mayapy.clear()
        for item in interpreters:
            self.combo_mayapy.addItem(
                "{} ({})".format(item["version"], item["path"]),
                item["path"],
            )
        if not interpreters:
            self.combo_mayapy.addItem("System Python ({})".format(sys.executable), sys.executable)

    def _browse_mayapy(self):
        cand, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Maya Python Interpreter (mayapy.exe)",
            r"C:\Program Files\Autodesk",
            "Executables (*.exe)",
        )
        if cand:
            norm = os.path.normpath(cand)
            self.combo_mayapy.insertItem(0, "Custom ({})".format(norm), norm)
            self.combo_mayapy.setCurrentIndex(0)

    def _toggle_console(self):
        self.log_console.setVisible(not self.log_console.isVisible())

    def _add_scenes_dialog(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Select Maya Animation Scenes to Export",
            "",
            "Maya Scenes (*.ma *.mb)",
        )
        if files:
            self.add_scene_files(files)

    def add_scene_files(self, file_paths):
        """Append scene files to batch queue."""
        seen = {item["path"].lower() for item in self.queue_items}
        added = 0
        from scartools.framework.naming import parse_shot_scene_identity

        for fp in file_paths:
            norm = os.path.normpath(fp).replace("\\", "/")
            if norm.lower() in seen:
                continue
            seen.add(norm.lower())

            identity = parse_shot_scene_identity(norm)
            shot_name = identity.get("shot_name") or os.path.splitext(os.path.basename(norm))[0]

            self.queue_items.append({
                "path": norm,
                "shot_name": shot_name,
                "status": "Ready",
            })
            added += 1

        self._refresh_table()

    def _remove_selected(self):
        selected_rows = sorted(
            [idx.row() for idx in self.queue_table.selectionModel().selectedRows()],
            reverse=True,
        )
        for row in selected_rows:
            if 0 <= row < len(self.queue_items):
                del self.queue_items[row]
        self._refresh_table()

    def _clear_all(self):
        if self.is_processing:
            return
        self.queue_items = []
        self._refresh_table()

    def _refresh_table(self):
        self.queue_table.setRowCount(len(self.queue_items))
        fmt_label = "Both" if self.combo_format.currentIndex() == 0 else ("Alembic" if self.combo_format.currentIndex() == 1 else "FBX")
        ver_text = self.combo_version.currentText()
        v_short = "Auto" if "next" in ver_text.lower() else ver_text

        for row, item in enumerate(self.queue_items):
            # 0: File Name
            f_item = QtWidgets.QTableWidgetItem(os.path.basename(item["path"]))
            f_item.setToolTip(item["path"])
            # 1: Shot Name
            s_item = QtWidgets.QTableWidgetItem(item["shot_name"])
            # 2: Version
            v_item = QtWidgets.QTableWidgetItem(v_short)
            v_item.setTextAlignment(QtCore.Qt.AlignCenter)
            # 3: Format
            m_item = QtWidgets.QTableWidgetItem(fmt_label)
            m_item.setTextAlignment(QtCore.Qt.AlignCenter)
            # 4: Status
            st = item["status"]
            st_item = QtWidgets.QTableWidgetItem(st)
            st_item.setTextAlignment(QtCore.Qt.AlignCenter)
            if st == "Ready":
                st_item.setForeground(QtGui.QColor(COLOR_TEXT_MUTED))
            elif "Exporting" in st:
                st_item.setForeground(QtGui.QColor(COLOR_PRIMARY_BLUE))
                st_item.setFont(QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold))
            elif st == "Done":
                st_item.setForeground(QtGui.QColor(COLOR_STATUS_SUCCESS))
                st_item.setFont(QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold))
            elif st == "Failed":
                st_item.setForeground(QtGui.QColor(COLOR_STATUS_ERROR))
                st_item.setFont(QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold))

            for col, w_item in enumerate((f_item, s_item, v_item, m_item, st_item)):
                w_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                self.queue_table.setItem(row, col, w_item)

        count = len(self.queue_items)
        self.count_badge.setText("{} scene(s) in queue".format(count))
        self.apply_button.setEnabled(count > 0 and not self.is_processing)
        self.apply_button.setText("START BATCH EXPORT ({} SHOTS)".format(count) if count > 0 else "START BATCH EXPORT")

    def start_batch_export(self):
        """Begin sequential queue execution in the background."""
        if not self.queue_items or self.is_processing:
            return

        self.is_processing = True
        self.btn_cancel.setVisible(True)
        self.apply_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_dot.set_status("running", "Exporting Batch")

        self._process_next_in_queue(0)

    def _process_next_in_queue(self, index):
        if index >= len(self.queue_items):
            # Batch Complete
            self.is_processing = False
            self.btn_cancel.setVisible(False)
            self.apply_button.setEnabled(True)
            self.progress_bar.setValue(100)
            self.status_dot.set_status("success", "Batch Complete")
            self.message_label.setText("Batch export complete for all {} scene(s)!".format(len(self.queue_items)))
            return

        item = self.queue_items[index]
        item["status"] = "Exporting..."
        self._refresh_table()

        mayapy_path = self.combo_mayapy.currentData()
        if not mayapy_path:
            txt = self.combo_mayapy.currentText()
            import re
            m = re.search(r"\((.+?\.exe)\)", txt, re.IGNORECASE)
            mayapy_path = m.group(1) if m else txt

        fmt_val = "both" if self.combo_format.currentIndex() == 0 else ("abc" if self.combo_format.currentIndex() == 1 else "fbx")
        ver_text = self.combo_version.currentText()
        ver_val = "next" if "next" in ver_text.lower() else ver_text
        handles = self.spin_handles.value()

        def _on_prog(pct, msg, **kwargs):
            self.job_progress_signal.emit(int(pct), str(msg))

        def _on_log(line):
            self.job_log_signal.emit(str(line))

        def _on_done(result, error):
            self.job_finished_signal.emit(index, bool(error is None), str(error or ""))

        self.current_job = BackgroundExportJob(
            scene_path=item["path"],
            version=ver_val,
            format_mode=fmt_val,
            handles=handles,
            mayapy_path=mayapy_path,
            on_progress=_on_prog,
            on_log=_on_log,
            on_finished=_on_done,
        )
        self.message_label.setText("Exporting scene {}/{} ('{}')...".format(index + 1, len(self.queue_items), item["shot_name"]))
        self.current_job.start()

    @QtCore.Slot(int, str)
    def _handle_progress(self, pct, msg):
        self.progress_bar.setValue(pct)
        self.message_label.setText(msg)

    @QtCore.Slot(str)
    def _handle_log(self, line):
        self.log_console.appendPlainText(line)

    @QtCore.Slot(int, bool, str)
    def _handle_job_done(self, index, success, error_msg):
        if 0 <= index < len(self.queue_items):
            self.queue_items[index]["status"] = "Done" if success else "Failed"
            self._refresh_table()

        if not success and error_msg:
            self.log_console.appendPlainText("JOB ERROR: {}".format(error_msg))

        if self.is_processing:
            self._process_next_in_queue(index + 1)

    def cancel_export(self):
        """Cancel the active job and stop the queue."""
        if self.current_job:
            self.current_job.cancel()
        self.is_processing = False
        self.btn_cancel.setVisible(False)
        self.apply_button.setEnabled(True)
        self.status_dot.set_status("warning", "Cancelled")
        self.message_label.setText("Batch export was cancelled.")


def main():
    """Launch the standalone desktop application."""
    app = QtWidgets.QApplication.instance()
    owns_app = False
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
        owns_app = True

    dialog = AnimExportStandaloneApp()
    dialog.show()

    if owns_app:
        sys.exit(app.exec_())


if __name__ == "__main__":
    main()
