"""ScarTools-styled Character Finalizer window."""

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
    FORM_ACTION_WIDTH,
    configure_field,
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
    finalize_character,
    inspect_character,
    resolve_space_switch_path,
    selected_namespace,
)
from scartools.version import VERSION


class CharacterFinalizerWindow(BaseToolDialog):
    """Preflight-first character finalization interface."""

    OBJECT_NAME = "ScarToolsCharacterFinalizerWindow"
    TOOL_ID = "character_finalizer"
    SMD_SETTING = "CharacterFinalizer_SmdPath"

    def __init__(self, parent=None):
        super(CharacterFinalizerWindow, self).__init__(
            parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle("Character Finalizer")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        configure_window(self, (790, 670), (850, 710))
        apply_window_icon(self)
        self._report = None
        self._log_dialog = None
        self._progress_popup = None
        self._build_ui()
        self._connect()
        apply_theme(self)
        self._initialize_context()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        header, _subtitle = create_brand_header(
            "CHARACTER FINALIZER",
            "Preflight, build, repair, and validate a character rig",
            parent=self,
        )
        self.overflow_btn = create_button("⋮", role="secondary", fixed_width=32, parent=self)
        self.overflow_btn.setObjectName("HeaderOverflowButton")
        self.overflow_btn.setToolTip("More Options")
        header.layout().addWidget(self.overflow_btn, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        root.addWidget(header)

        context_group, context_layout, _context_title = create_section_panel(
            "Rig Context", accent="rig", layout_kind="grid", parent=self
        )
        context_layout.setColumnStretch(1, 1)

        namespace_label = QtWidgets.QLabel("Namespace")
        self.namespace_edit = QtWidgets.QLineEdit()
        self.namespace_edit.setPlaceholderText("Root namespace")
        configure_field(self.namespace_edit)
        self.detect_button = create_button(
            "Detect from Selection", fixed_width=FORM_ACTION_WIDTH
        )

        smd_label = QtWidgets.QLabel("Space-switch SMD")
        self.smd_edit = QtWidgets.QLineEdit()
        self.smd_edit.setPlaceholderText("Select Arm_Follow_Space_Switch_V001.smd")
        configure_field(self.smd_edit)
        self.browse_button = create_button(
            "Browse", fixed_width=FORM_ACTION_WIDTH
        )

        context_layout.addWidget(namespace_label, 0, 0)
        context_layout.addWidget(self.namespace_edit, 0, 1)
        context_layout.addWidget(self.detect_button, 0, 2)
        context_layout.addWidget(smd_label, 1, 0)
        context_layout.addWidget(self.smd_edit, 1, 1)
        context_layout.addWidget(self.browse_button, 1, 2)
        root.addWidget(context_group)

        preflight_group, preflight_layout, _preflight_title = create_section_panel(
            "Preflight", accent="validation", parent=self
        )

        self.summary_badge = QtWidgets.QLabel("Not checked")
        self.summary_badge.setObjectName("CountBadge")
        self.preflight_button = create_button(
            "Run Preflight", fixed_width=FORM_ACTION_WIDTH
        )
        preflight_group.add_header_action(self.summary_badge)
        preflight_group.add_header_action(self.preflight_button)

        self.preflight_table = create_data_table(
            ["Check", "Status", "Details"],
            stretch_columns=(2,),
            contents_columns=(0, 1),
            minimum_height=260,
            parent=self,
        )
        preflight_layout.addWidget(self.preflight_table, 1)
        root.addWidget(preflight_group, 1)

        (
            action_footer,
            self.warning_label,
            self.finalize_button,
            self.status_dot,
            self.status_label,
            self.view_log_button,
            _status_layout,
        ) = create_action_footer(
            "FINALIZE CHARACTER",
            message="Run Preflight before finalizing the character.",
            parent=self,
        )
        self.finalize_button.setProperty("mode", "export")
        self.finalize_button.setEnabled(False)
        root.addWidget(action_footer)

        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.hide()

    def _connect(self):
        self.detect_button.clicked.connect(self._detect_namespace)
        self.browse_button.clicked.connect(self._browse_smd)
        self.preflight_button.clicked.connect(self._run_preflight)
        self.finalize_button.clicked.connect(self._finalize)
        self.view_log_button.clicked.connect(self._show_log)
        self.namespace_edit.textChanged.connect(self._invalidate)
        self.smd_edit.textChanged.connect(self._invalidate)

    def _initialize_context(self):
        self.namespace_edit.setText(selected_namespace())
        saved = settings.get_string(self.SMD_SETTING, "")
        self.smd_edit.setText(resolve_space_switch_path(saved))
        self._run_preflight()

    def _detect_namespace(self):
        self.namespace_edit.setText(selected_namespace())
        self._run_preflight()

    def _browse_smd(self):
        start = self.smd_edit.text().strip()
        if start and os.path.isfile(start):
            start = os.path.dirname(start)
        result = cmds.fileDialog2(
            fileMode=1,
            caption="Select Space Manager SMD",
            fileFilter="Space Manager Dictionary (*.smd)",
            startingDirectory=start or os.path.expanduser("~"),
        )
        if not result:
            return
        path = os.path.normpath(result[0])
        self.smd_edit.setText(path)
        settings.set_string(self.SMD_SETTING, path)
        self._run_preflight()

    def _invalidate(self, *_):
        self._report = None
        self.finalize_button.setEnabled(False)
        self.summary_badge.setText("Preflight required")

    @staticmethod
    def _item(text, color=None):
        item = QtWidgets.QTableWidgetItem(str(text))
        if color:
            item.setForeground(QtGui.QColor(color))
        return item

    def _run_preflight(self):
        self.preflight_table.setRowCount(0)
        try:
            self._report = inspect_character(
                namespace=self.namespace_edit.text(),
                smd_path=self.smd_edit.text(),
            )
        except Exception as exc:
            self._report = None
            self._set_warning(str(exc), "error")
            self._set_status("Preflight failed", "error")
            self.finalize_button.setEnabled(False)
            return

        checks = self._report["checks"]
        self.preflight_table.setRowCount(len(checks))
        colors = {
            "Ready": "#72D6AA",
            "Create": "#5C87C8",
            "Repair": "#D6B36A",
            "Unlock": "#D6B36A",
            "Missing": "#E06C6C",
            "Blocked": "#E06C6C",
        }
        for row, check in enumerate(checks):
            self.preflight_table.setItem(row, 0, self._item(check["label"]))
            self.preflight_table.setItem(
                row, 1, self._item(check["status"], colors.get(check["status"]))
            )
            self.preflight_table.setItem(row, 2, self._item(check["message"]))

        blockers = len(self._report["blocking"])
        self.summary_badge.setText(
            "READY" if not blockers else "{} BLOCKER(S)".format(blockers)
        )
        self.finalize_button.setEnabled(not blockers)
        if blockers:
            self._set_warning(
                "Resolve the highlighted blockers before finalizing.", "error"
            )
            self._set_status("Preflight blocked", "error")
        else:
            self._set_warning(
                "Ready. Locked scale and destination plugs will be unlocked; "
                "connections are applied forcefully in one undo step.",
                "success",
            )
            self._set_status("Preflight passed", "success")
        self.log_box.clear()
        self.log_box.appendPlainText("=" * 72)
        self.log_box.appendPlainText("INFO: CHARACTER FINALIZER — PREFLIGHT REPORT")
        self.log_box.appendPlainText("INFO: Namespace: '{}' | Space-Switch SMD: '{}'".format(
            self._report["namespace"] or "<root>", os.path.basename(self.smd_edit.text()) if self.smd_edit.text() else "<None>"
        ))
        self.log_box.appendPlainText("=" * 72)

        for check in checks:
            status = check["status"]
            label = check["label"]
            msg = check["message"]
            if status in ("Blocked", "Missing"):
                self.log_box.appendPlainText("ERROR: ❌ [{}] — Status: {} | {}".format(label, status, msg))
            elif status in ("Repair", "Unlock", "Create"):
                self.log_box.appendPlainText("WARNING: ⚠️ [{}] — Status: {} | {}".format(label, status, msg))
            elif status == "Ready":
                self.log_box.appendPlainText("SUCCESS: ✓ [{}] — {}".format(label, msg))
            else:
                self.log_box.appendPlainText("INFO: [{}] — Status: {} | {}".format(label, status, msg))

        self.log_box.appendPlainText("\n" + "=" * 72)
        if blockers:
            self.log_box.appendPlainText("ERROR: Summary: {} Blocker(s) detected. Fix highlighted issues before finalization.".format(blockers))
        else:
            self.log_box.appendPlainText("SUCCESS: ✓ Rig is 100% Ready for Finalization (All checks passed/ready).")
        self.log_box.appendPlainText("=" * 72 + "\n")

    def _finalize(self):
        if not self._report or not self._report["ok"]:
            self._run_preflight()
            if not self._report or not self._report["ok"]:
                return

        answer = QtWidgets.QMessageBox.question(
            self,
            "Finalize Character",
            "Finalize namespace '{}'?\n\nThe complete operation is one Maya undo step.".format(
                self._report["namespace"] or "<root>"
            ),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return

        self.log_box.appendPlainText("\n" + "=" * 72)
        self.log_box.appendPlainText("INFO: STARTING CHARACTER FINALIZATION...")
        self.log_box.appendPlainText("=" * 72)

        self._progress_popup = OperationProgressPopup(
            title="Character Finalizer - Processing", parent=self
        )
        self._progress_popup.start("Finalizing Character", 7)
        self._set_status("Finalizing character...", "running")
        self.finalize_button.setEnabled(False)
        try:
            result = finalize_character(
                namespace=self.namespace_edit.text(),
                smd_path=self.smd_edit.text(),
                log=self._log,
                progress=self._progress_popup.update_progress,
            )
            self._progress_popup.update_progress(100, "Validation complete")
            self._progress_popup.finish()
            self._progress_popup = None
            self._set_warning(
                "Character finalized successfully. Use Ctrl+Z to undo the complete operation.",
                "success",
            )
            self._set_status("Finalization complete", "success")
            self._log(
                "SUCCESS: ✓ Unlocked {} scale plug(s); removed {} legacy attribute(s).".format(
                    len(result["unlocked_scale"]), len(result["legacy_removed"])
                )
            )
            self._log("SUCCESS: ✓ Character finalized in 1 unified Maya undo step.")
            self._run_preflight()
        except Exception as exc:
            if self._progress_popup:
                self._progress_popup.close()
                self._progress_popup.deleteLater()
                self._progress_popup = None
            self._log("ERROR: {}".format(exc))
            self._set_warning(str(exc), "error")
            self._set_status("Finalization failed and rolled back", "error")
            QtWidgets.QMessageBox.critical(self, "Character Finalizer", str(exc))
            self._run_preflight()

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
            emit_log(message, source="Character Finalizer")
        except Exception:
            pass
        QtWidgets.QApplication.processEvents()

    def _show_log(self):
        try:
            from scartools.ui.logs import show_global_log
            show_global_log(source="Character Finalizer", parent=self)
        except Exception:
            pass




_window = None


def show_ui():
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

    _window = CharacterFinalizerWindow(parent=maya_main_window())
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
    close_tool_windows("character_finalizer")


__all__ = ["CharacterFinalizerWindow", "close_all_windows", "show_ui"]
