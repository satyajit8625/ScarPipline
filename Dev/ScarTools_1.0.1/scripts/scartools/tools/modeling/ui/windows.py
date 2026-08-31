# -*- coding: utf-8 -*-
"""Qt User Interface for Modeling & Scene Sanitizer."""

from __future__ import print_function

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
    create_popup_menu,
    create_data_table,
    create_section_panel,
    repolish,
)
from scartools.ui.tokens import (
    FORM_ACTION_WIDTH,
    TABLE_STATUS_WIDTH,
)
from ..operations import (
    inspect_model_and_scene,
    select_issue_components,
    fix_all_safe_issues,
    fix_make_names_unique,
    fix_add_geo_suffixes,
    fix_add_grp_suffixes,
    fix_shader_suffixes,
    fix_freeze_transforms,
    fix_center_pivots,
    fix_delete_construction_history,
    fix_delete_intermediate_shapes,
    fix_unlock_normals,
    fix_clean_scene_clutter,
)


class ModelSanitizerWindow(BaseToolDialog):
    """ScarTools preflight QA dashboard for 3D modeling and scene hygiene."""

    OBJECT_NAME = "ScarToolsModelSanitizerWindow"
    TOOL_ID = "model_sanitizer"

    FIXABLE_CHECKS = {
        "duplicate_names": fix_make_names_unique,
        "mesh_suffixes": fix_add_geo_suffixes,
        "group_suffixes": fix_add_grp_suffixes,
        "material_suffixes": fix_shader_suffixes,
        "shading_group_suffixes": fix_shader_suffixes,
        "unfrozen_transforms": fix_freeze_transforms,
        "negative_scales": fix_freeze_transforms,
        "intermediate_shapes": fix_delete_intermediate_shapes,
        "construction_history": fix_delete_construction_history,
        "empty_groups": fix_clean_scene_clutter,
        "root_pivot": fix_center_pivots,
        "geometry_pivots": fix_center_pivots,
        "locked_normals": fix_unlock_normals,
        "display_layers": fix_clean_scene_clutter,
        "anim_layers": fix_clean_scene_clutter,
        "unknown_nodes": fix_clean_scene_clutter,
        "color_sets": fix_clean_scene_clutter,
    }

    def __init__(self, parent=None):
        super(ModelSanitizerWindow, self).__init__(
            parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle("Model & Scene Sanitizer")
        apply_window_icon(self)
        configure_window(self, (820, 580), (880, 660))
        self._last_report = None
        self._log_dialog = None
        self._build_ui()
        self._connect()
        apply_theme(self)
        self._run_inspection()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        header, self.header_subtitle = create_brand_header(
            "MODEL & SCENE SANITIZER",
            "Preflight QA, topology, transforms, suffixes, and layer sanitization",
            parent=self,
        )
        self.overflow_btn = create_button("⋮", role="secondary", fixed_width=32, parent=self)
        self.overflow_btn.setObjectName("HeaderOverflowButton")
        self.overflow_btn.setToolTip("More Options")
        header.layout().addWidget(self.overflow_btn, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        root.addWidget(header)

        # Preflight QA Checks Panel (Centralized Suite Section Panel)
        checks_panel, checks_layout, _ = create_section_panel(
            "Preflight Checks", accent="validation", parent=self
        )

        self.summary_badge = QtWidgets.QLabel("Not checked")
        self.summary_badge.setObjectName("CountBadge")
        self.check_button = create_button(
            "Run Sanity Check", role="secondary", fixed_width=FORM_ACTION_WIDTH
        )
        self.check_button.setToolTip("Scan active Maya scene geometry and nodes against all 26 QA rules.")

        checks_panel.add_header_action(self.summary_badge)
        checks_panel.add_header_action(self.check_button)

        # Data Table (All 26 QA Checks)
        self.table = create_data_table(
            ["Status", "Severity", "Check Name", "Category", "Issues"],
            stretch_columns=(2,),
            fixed_columns={0: TABLE_STATUS_WIDTH, 1: 95, 3: 110, 4: 70},
            minimum_height=300,
            parent=self,
        )
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        checks_layout.addWidget(self.table, 1)
        root.addWidget(checks_panel, 1)

        # Centralized Action Footer
        (
            footer,
            self.warning_label,
            self.fix_all_button,
            self.status_dot,
            self.status_label,
            self.view_log_button,
            _,
        ) = create_action_footer(
            "FIX ALL SAFE ISSUES",
            message="Run Sanity Check to analyze the active scene.",
            parent=self,
        )
        self.fix_all_button.setEnabled(False)
        self.fix_all_button.setToolTip(
            "Automatically execute all safe, non-destructive fixes\n"
            "(freeze transforms, center pivots, delete history, apply _GEO/_GRP suffixes, unlock normals, purge clutter)\n"
            "in 1 unified Maya Ctrl+Z undo step."
        )
        root.addWidget(footer)

        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)

    def _connect(self):
        self.check_button.clicked.connect(self._run_inspection)
        self.fix_all_button.clicked.connect(self._run_fix_all)
        self.view_log_button.clicked.connect(self._show_log)
        self.table.itemDoubleClicked.connect(self._on_table_double_clicked)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)

    def _log(self, message):
        self.log_box.appendPlainText(str(message))
        try:
            from scartools.framework.logging import emit_log
            emit_log(message, source="Model Sanitizer")
        except Exception:
            pass
        bar = self.log_box.verticalScrollBar()
        bar.setValue(bar.maximum())
        QtWidgets.QApplication.processEvents()


    def _format_issue_item(self, node, info):
        if isinstance(info, dict):
            if "unmapped_faces" in info and info["unmapped_faces"]:
                return "{} ({} unmapped face(s))".format(node, len(info["unmapped_faces"]))
            if "has_uvs" in info and not info["has_uvs"]:
                return "{} (0 UV coordinates / missing UV set)".format(node)
            if "faces" in info:
                return "{} ({} face(s))".format(node, len(info["faces"]))
            if "edges" in info:
                return "{} ({} edge(s))".format(node, len(info["edges"]))
            if "vertices" in info:
                return "{} ({} vertex/vertices)".format(node, len(info["vertices"]))
            if "expected" in info:
                return "{} (rename to '{}')".format(node, info["expected"])
            if "sanitized" in info:
                return "{} (illegal chars -> rename to '{}')".format(node, info["sanitized"])
            if "material" in info:
                return "{} (default material '{}' assigned)".format(node, info["material"])
            if "color_sets" in info:
                return "{} (vertex color set(s): {})".format(node, ", ".join(info["color_sets"]))
            if "pivot" in info:
                piv = info["pivot"]
                return "{} (pivot offset: [{:.3f}, {:.3f}, {:.3f}])".format(node, piv[0], piv[1], piv[2])
            if "count" in info:
                return "{} ({} issue(s))".format(node, info["count"])
        elif isinstance(info, list):
            return "{} ({})".format(node, ", ".join([str(x) for x in info[:5]]))
        return str(node)

    def _log_inspection_report(self, report):
        self.log_box.clear()
        crit = report["critical_count"]
        warn = report["warning_count"]
        meshes = report["mesh_count"]
        status = report["overall_status"]

        self.log_box.appendPlainText("=" * 72)
        self.log_box.appendPlainText("INFO: MODEL & SCENE SANITIZER — PREFLIGHT QA REPORT")
        self.log_box.appendPlainText("INFO: Scanned: {} mesh transform(s) | Overall Status: {}".format(meshes, status))
        self.log_box.appendPlainText("=" * 72)

        if crit == 0 and warn == 0:
            self.log_box.appendPlainText("\nSUCCESS: ✓ All 26 preflight QA checks passed. Scene is 100% clean and certified.")
            self.log_box.appendPlainText("SUCCESS: Certified good to go for rigging and downstream pipeline.")
            self.log_box.appendPlainText("=" * 72 + "\n")
            return

        # Critical Blockers
        if crit > 0:
            self.log_box.appendPlainText("\nERROR: ------------------------------------------------------------")
            self.log_box.appendPlainText("ERROR: ❌ CRITICAL BLOCKERS ({} check(s) failed):".format(crit))
            self.log_box.appendPlainText("ERROR: ------------------------------------------------------------")
            for key, check in report["checks"].items():
                if not check["passed"] and check["severity"] == "CRITICAL":
                    count_str = check["issue_count"]
                    self.log_box.appendPlainText("ERROR: [{}] — {} issue(s) found:".format(check["name"], count_str))
                    data = check["data"]
                    if isinstance(data, dict):
                        # Filter out helper keys like 'count'
                        items = [(k, v) for k, v in data.items() if k not in ("count", "shape")]
                        for i, (node, info) in enumerate(items[:20]):
                            formatted = self._format_issue_item(node, info)
                            self.log_box.appendPlainText("ERROR:   • {}".format(formatted))
                        if len(items) > 20:
                            self.log_box.appendPlainText("ERROR:   • ... and {} more issue(s) (double-click table row to select all)".format(len(items) - 20))
                    self.log_box.appendPlainText("ERROR:   Description: {}".format(check["description"]))

        # Pipeline Warnings
        if warn > 0:
            self.log_box.appendPlainText("\nWARNING: ------------------------------------------------------------")
            self.log_box.appendPlainText("WARNING: ⚠️ PIPELINE WARNINGS ({} check(s) flagged):".format(warn))
            self.log_box.appendPlainText("WARNING: ------------------------------------------------------------")
            for key, check in report["checks"].items():
                if not check["passed"] and check["severity"] == "WARNING":
                    count_str = check["issue_count"]
                    self.log_box.appendPlainText("WARNING: [{}] — {} issue(s) found:".format(check["name"], count_str))
                    data = check["data"]
                    if isinstance(data, dict):
                        items = [(k, v) for k, v in data.items() if k not in ("count", "shape")]
                        for i, (node, info) in enumerate(items[:20]):
                            formatted = self._format_issue_item(node, info)
                            self.log_box.appendPlainText("WARNING:   • {}".format(formatted))
                        if len(items) > 20:
                            self.log_box.appendPlainText("WARNING:   • ... and {} more issue(s) (double-click table row to select all)".format(len(items) - 20))
                    self.log_box.appendPlainText("WARNING:   Description: {}".format(check["description"]))

        self.log_box.appendPlainText("\n" + "=" * 72)
        summary_title = "ERROR: Summary: Found {} Critical Error(s), {} Warning(s)." if crit > 0 else "WARNING: Summary: Found {} Warning(s)."
        self.log_box.appendPlainText(summary_title.format(crit, warn))
        self.log_box.appendPlainText("INFO: Double-click any row in the table above to highlight offending components in viewport.")
        self.log_box.appendPlainText("INFO: Click 'FIX ALL SAFE ISSUES' to auto-resolve safe naming, transform, and clutter issues.")
        self.log_box.appendPlainText("=" * 72 + "\n")

    def _set_status(self, text, state="idle"):
        self.status_label.setText(str(text))
        self.status_label.setProperty("state", state)
        self.status_dot.setProperty("state", state)
        repolish(self.status_label)
        repolish(self.status_dot)

    def _run_inspection(self):
        self._set_status("Inspecting model and scene...", "busy")
        QtWidgets.QApplication.processEvents()

        report = inspect_model_and_scene()
        self._last_report = report
        self._populate_table()

        crit = report["critical_count"]
        warn = report["warning_count"]
        passed = (crit == 0 and warn == 0)

        if passed:
            self.summary_badge.setText("All 26 checks passed (100% clean)")
            self.warning_label.setText("Scene is 100% clean — certified good to go for rigging & pipeline.")
            self.warning_label.setProperty("state", "neutral")
            self.fix_all_button.setEnabled(False)
            self._set_status("Passed — 100% clean", "success")
        else:
            summary = "Found {} critical, {} warnings".format(crit, warn)
            self.summary_badge.setText(summary)
            self.warning_label.setText("Review issues above or click FIX ALL SAFE ISSUES.")
            self.warning_label.setProperty("state", "warning")
            self.fix_all_button.setEnabled(True)
            state_key = "error" if crit > 0 else "warning"
            self._set_status(summary, state_key)

        repolish(self.warning_label)
        self._log_inspection_report(report)


    def _populate_table(self):
        if not self._last_report:
            return

        checks = self._last_report["checks"]
        check_keys = list(checks.keys())

        self.table.setRowCount(len(check_keys))
        for row, key in enumerate(check_keys):
            check = checks[key]
            passed = check["passed"]
            severity = check["severity"]

            status_str = "PASS" if passed else "FAIL"
            status_item = QtWidgets.QTableWidgetItem(status_str)
            status_item.setTextAlignment(QtCore.Qt.AlignCenter)
            status_item.setData(QtCore.Qt.UserRole, key)
            status_item.setForeground(
                QtGui.QColor("#72d6aa") if passed else QtGui.QColor("#f07d7d" if severity == "CRITICAL" else "#f6ad55")
            )
            self.table.setItem(row, 0, status_item)

            sev_str = "PASSED" if passed else severity
            sev_item = QtWidgets.QTableWidgetItem(sev_str)
            sev_item.setTextAlignment(QtCore.Qt.AlignCenter)
            sev_item.setData(QtCore.Qt.UserRole, key)
            sev_item.setForeground(
                QtGui.QColor("#72d6aa") if passed else QtGui.QColor("#f07d7d" if severity == "CRITICAL" else "#f6ad55")
            )
            self.table.setItem(row, 1, sev_item)

            name_item = QtWidgets.QTableWidgetItem(check["name"])
            name_item.setToolTip(check["description"])
            name_item.setData(QtCore.Qt.UserRole, key)
            self.table.setItem(row, 2, name_item)

            cat_item = QtWidgets.QTableWidgetItem(check["category"])
            cat_item.setTextAlignment(QtCore.Qt.AlignCenter)
            cat_item.setData(QtCore.Qt.UserRole, key)
            self.table.setItem(row, 3, cat_item)

            issues_txt = "0" if passed else str(check["issue_count"])
            cnt_item = QtWidgets.QTableWidgetItem(issues_txt)
            cnt_item.setTextAlignment(QtCore.Qt.AlignCenter)
            cnt_item.setData(QtCore.Qt.UserRole, key)
            if not passed:
                cnt_item.setForeground(QtGui.QColor("#f07d7d" if severity == "CRITICAL" else "#f6ad55"))
            self.table.setItem(row, 4, cnt_item)

    def _on_table_double_clicked(self, item):
        if not item:
            return
        check_key = item.data(QtCore.Qt.UserRole)
        if check_key:
            self._select_check(check_key)

    def _show_table_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        name_item = self.table.item(row, 2)
        if not name_item:
            return
        check_key = name_item.data(QtCore.Qt.UserRole)
        if not check_key:
            return

        menu = create_popup_menu(parent=self)

        if not passed:
            select_action = menu.addAction("◇   Select in Viewport")
            select_action.setToolTip("Highlight all offending components/objects in Maya 3D viewport")
        else:
            select_action = menu.addAction("✓   Check Passed")
            select_action.setEnabled(False)

        fix_action = None
        if check_key in self.FIXABLE_CHECKS:
            fix_action = menu.addAction("⚡   Fix This Issue")
            fix_action.setEnabled(not passed)
            fix_action.setToolTip("Execute safe automated fix for this check")

        action = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if action == select_action and not passed:
            self._select_check(check_key)
        elif fix_action and action == fix_action:
            self._fix_single_check(check_key)

    def _select_check(self, check_key):
        selected = select_issue_components(check_key)
        self._log("Selected {} component(s) for check '{}'.".format(len(selected), check_key))
        if selected:
            self._set_status(
                "Selected {} issue component(s) in viewport".format(len(selected)), "warning"
            )

    def _fix_single_check(self, check_key):
        fix_fn = self.FIXABLE_CHECKS.get(check_key)
        if fix_fn:
            self._log("\nINFO: ------------------------------------------------------------")
            self._log("INFO: Running automated fix for '{}'...".format(check_key))
            try:
                fix_fn(log=self._log)
                self._log("SUCCESS: ✓ Completed fix for '{}'.".format(check_key))
            except Exception as exc:
                self._log("ERROR: Fix failed -> {}".format(exc))
            self._log("INFO: ------------------------------------------------------------\n")
        else:
            self._log("WARNING: Manual artist decision required for '{}' — inspect selected components.".format(check_key))
            select_issue_components(check_key)

        self._run_inspection()

    def _run_fix_all(self):
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Fix All Safe Issues",
            "This will automatically freeze transforms, center pivots, delete history, "
            "apply _GEO/_GRP/_SHD/_SG suffixes, unlock normals, and purge scene clutter.\n\n"
            "Proceed in 1 atomic undo step?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        self._log("\n" + "=" * 72)
        self._log("INFO: STARTING FIX ALL SAFE ISSUES...")
        self._log("=" * 72)
        try:
            fix_all_safe_issues(log=self._log)
            self._log("\nSUCCESS: ✓ Completed Fix All Safe Issues in 1 atomic undo step.")
        except Exception as exc:
            self._log("ERROR: Fix all failed -> {}".format(exc))
        self._log("=" * 72 + "\n")
        self._run_inspection()


    def _show_log(self):
        try:
            from scartools.ui.logs import show_global_log
            show_global_log(source="Model Sanitizer", parent=self)
        except Exception:
            pass



_tool_instance = None

def show_ui():
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

    _tool_instance = ModelSanitizerWindow(parent=maya_main_window())
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

