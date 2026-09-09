# -*- coding: utf-8 -*-
"""Streamlined, 1-click Qt User Interface for UDIM Texture Preview Generator."""

from __future__ import print_function

import os
import maya.cmds as cmds

from scartools.ui.qt import (
    QtCore,
    QtGui,
    QtWidgets,
    apply_window_icon,
    maya_main_window,
)
from scartools.ui import (
    BaseToolDialog,
    LogDialog,
    apply_theme,
    configure_root_layout,
    configure_window,
    create_action_footer,
    create_brand_header,
    create_button,
    create_data_table,
    create_section_panel,
    repolish,
)
from ..operations import (
    scan_udim_textures,
    generate_all_udim_previews,
    convert_selected_to_udim,
)


class UDIMManagerWindow(BaseToolDialog):
    """Minimal, fast 1-click tool to audit and generate Viewport 2.0 UDIM tile previews."""

    OBJECT_NAME = "ScarToolsUDIMManagerWindow"
    TOOL_ID = "udim_manager"

    def __init__(self, parent=None):
        super(UDIMManagerWindow, self).__init__(
            parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle("UDIM Preview Generator")
        apply_window_icon(self)
        configure_window(self, (640, 460), (720, 520))
        self._last_report = None
        self._log_dialog = None
        self._build_ui()
        self._connect()
        apply_theme(self)
        self._run_scan()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)
        root.setSpacing(8)

        # Header
        header, _ = create_brand_header(
            "UDIM PREVIEW GENERATOR",
            "Generate & reload Viewport 2.0 texture previews for multi-tile UVs",
            parent=self,
        )
        root.addWidget(header)

        # Main Table Panel
        panel, layout, _ = create_section_panel(
            "UDIM Textures in Scene", accent="texturing", parent=self
        )

        top_bar = QtWidgets.QHBoxLayout()
        self.summary_badge = QtWidgets.QLabel("Scanning...")
        self.summary_badge.setObjectName("CountBadge")

        self.refresh_btn = create_button("Refresh", role="secondary", fixed_width=80)
        self.refresh_btn.setToolTip("Re-scan scene for newly assigned textures.")

        top_bar.addWidget(self.summary_badge)
        top_bar.addStretch(1)
        top_bar.addWidget(self.refresh_btn)
        layout.addLayout(top_bar)

        # Data Table
        self.table = create_data_table(
            ["Node Name", "Tiles", "Missing Gaps", "Material", "Status"],
            stretch_columns=(0, 3),
            fixed_columns={1: 65, 2: 120, 4: 90},
            minimum_height=200,
            parent=self,
        )
        self.table.setToolTip("Double-click any row to select that file node in Maya.")
        layout.addWidget(self.table, 1)
        root.addWidget(panel, 1)

        # Standard Centralized Action Footer
        (
            action_footer,
            self.warning_label,
            self.generate_button,
            self.status_dot,
            self.status_label,
            self.view_log_button,
            _status_layout,
        ) = create_action_footer(
            "GENERATE ALL UDIM PREVIEWS",
            message="Scan scene textures and generate Viewport 2.0 multi-tile previews.",
            parent=self,
            include_log=False,
        )
        self.generate_button.setToolTip(
            "Automatically converts numbered file paths to <UDIM> format,\n"
            "generates UV tile proxy previews, and reloads Viewport 2.0 graphics cache."
        )
        root.addWidget(action_footer)

        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)

    def _connect(self):
        self.refresh_btn.clicked.connect(self._run_scan)
        self.generate_button.clicked.connect(self._run_generate_previews)
        self.view_log_button.clicked.connect(self._show_log)
        self.table.itemDoubleClicked.connect(self._on_table_double_clicked)

    def _log(self, message):
        self.log_box.appendPlainText(str(message))
        bar = self.log_box.verticalScrollBar()
        bar.setValue(bar.maximum())
        QtWidgets.QApplication.processEvents()

    def _set_status(self, text, state="idle"):
        self.status_label.setText(str(text))
        self.status_label.setProperty("state", state)
        self.status_dot.setProperty("state", state)
        repolish(self.status_label)
        repolish(self.status_dot)

    def _run_scan(self):
        self._set_status("Scanning scene file textures...", "busy")
        QtWidgets.QApplication.processEvents()

        report = scan_udim_textures()
        self._last_report = report
        self._populate_table()
        self._log_scan_report(report)

        udim_cnt = report["udim_files_count"]
        missing_cnt = report["missing_tiles_total"]

        summary = "{} UDIM Texture(s) Found".format(udim_cnt)
        if missing_cnt > 0:
            summary += " — {} missing tile(s)!".format(missing_cnt)
            self._set_status("{} missing tile(s) detected".format(missing_cnt), "warning")
        else:
            self._set_status("Ready to generate previews", "idle")

        self.summary_badge.setText(summary)

    def _populate_table(self):
        if not self._last_report:
            return

        nodes_dict = self._last_report.get("nodes", {})
        # Show all UDIM nodes or nodes with multiple tiles
        udim_rows = [(k, v) for k, v in nodes_dict.items() if v["is_udim"]]

        # If no UDIM nodes, show any single textures so artist can see what is in scene
        if not udim_rows:
            udim_rows = list(nodes_dict.items())

        self.table.setRowCount(len(udim_rows))

        for row, (node_name, info) in enumerate(udim_rows):
            # 0: Node Name
            item_name = QtWidgets.QTableWidgetItem(node_name)
            item_name.setToolTip(info["fileTextureName"])
            item_name.setData(QtCore.Qt.UserRole, node_name)
            self.table.setItem(row, 0, item_name)

            # 1: Tiles
            tiles_cnt = len(info["tiles"])
            item_tiles = QtWidgets.QTableWidgetItem(str(tiles_cnt))
            item_tiles.setTextAlignment(QtCore.Qt.AlignCenter)
            if info["is_udim"] and tiles_cnt > 0:
                item_tiles.setForeground(QtGui.QColor("#72D6AA"))
            self.table.setItem(row, 1, item_tiles)

            # 2: Missing Gaps
            missing = info["missing_tiles"]
            miss_str = ", ".join(str(x) for x in missing[:4]) if missing else "None"
            if len(missing) > 4:
                miss_str += "..."
            item_miss = QtWidgets.QTableWidgetItem(miss_str)
            item_miss.setTextAlignment(QtCore.Qt.AlignCenter)
            if missing:
                item_miss.setForeground(QtGui.QColor("#F07D7D"))
            self.table.setItem(row, 2, item_miss)

            # 3: Material
            mats = ", ".join(info["materials"]) if info["materials"] else "—"
            item_mats = QtWidgets.QTableWidgetItem(mats)
            self.table.setItem(row, 3, item_mats)

            # 4: Status
            if missing:
                status_txt = "MISSING"
                color = "#F07D7D"
            elif info["is_udim"]:
                status_txt = "OK"
                color = "#72D6AA"
            else:
                status_txt = "SINGLE"
                color = "#A0A0A0"

            item_status = QtWidgets.QTableWidgetItem(status_txt)
            item_status.setTextAlignment(QtCore.Qt.AlignCenter)
            item_status.setForeground(QtGui.QColor(color))
            self.table.setItem(row, 4, item_status)

    def _log_scan_report(self, report):
        self.log_box.clear()
        self._log("=" * 68)
        self._log("INFO: UDIM PREVIEW GENERATOR — SCENE SCAN REPORT")
        self._log("INFO: Total File Nodes: {} | UDIM Textures: {}".format(
            report["total_files"], report["udim_files_count"]
        ))
        self._log("=" * 68)

        for node_name, info in sorted(report["nodes"].items()):
            if info["is_udim"]:
                if info["missing_tiles"]:
                    self._log(
                        "ERROR: ❌ [{}] Missing Tile Gaps: {} | Path: {}".format(
                            node_name, ", ".join(str(x) for x in info["missing_tiles"]), info["fileTextureName"]
                        )
                    )
                else:
                    self._log(
                        "SUCCESS: ✓ [{}] {} tile(s) loaded (Tiles: {})".format(
                            node_name, len(info["tiles"]),
                            ", ".join(str(x) for x in info["tile_numbers"][:8]) + ("..." if len(info["tile_numbers"]) > 8 else "")
                        )
                    )
            else:
                self._log(
                    "INFO: • [{}] Single Texture: {}".format(node_name, os.path.basename(info["fileTextureName"]))
                )

        self._log("=" * 68)
        if report["missing_tiles_total"] > 0:
            self._log("WARNING: {} missing UDIM tile file(s) on disk.".format(report["missing_tiles_total"]))
        else:
            self._log("SUCCESS: ✓ All UDIM tile file paths exist continuously on disk.")
        self._log("INFO: Click 'GENERATE ALL UDIM PREVIEWS' to load into Viewport 2.0.")
        self._log("=" * 68)


    def _run_generate_previews(self):
        self._log("\n" + "=" * 68)
        self._log("INFO: GENERATING UDIM PREVIEWS & RELOADING VIEWPORT 2.0...")
        self._log("=" * 68)
        self._set_status("Generating UDIM previews...", "busy")

        try:
            # 1. Automatically convert any unformatted numbered textures to <UDIM>
            convert_selected_to_udim(log=self._log)
            # 2. Force hardware tile proxy generation and flush GPU cache
            count = generate_all_udim_previews(log=self._log)
            self._set_status("Generated previews for {} node(s)".format(count), "success")
        except Exception as exc:
            self._log("ERROR: UDIM preview generation failed -> {}".format(exc))
            self._set_status("Generation failed", "error")

        self._run_scan()

    def _on_table_double_clicked(self, item):
        if not item:
            return
        row = item.row()
        node_item = self.table.item(row, 0)
        if node_item:
            node_name = node_item.data(QtCore.Qt.UserRole)
            if node_name and cmds.objExists(node_name):
                cmds.select(node_name, replace=True)
    def _log(self, message):
        self.log_box.appendPlainText(str(message))
        try:
            from scartools.framework.logging import emit_log
            emit_log(message, source="UDIM Manager")
        except Exception:
            pass

    def _show_log(self):
        try:
            from scartools.ui.logs import show_global_log
            show_global_log(source="UDIM Manager", parent=self)
        except Exception:
            pass



_tool_instance = None

def show_ui():
    global _tool_instance
    try:
        if _tool_instance:
            _tool_instance.close()
            _tool_instance.deleteLater()
    except Exception:
        pass
    _tool_instance = UDIMManagerWindow(parent=maya_main_window())
    _tool_instance.show()
    _tool_instance.raise_()
    _tool_instance.activateWindow()
    return _tool_instance

def close_all_windows():
    global _tool_instance
    if _tool_instance:
        try:
            _tool_instance.close()
            _tool_instance.deleteLater()
        except Exception:
            pass
        _tool_instance = None
    return True
