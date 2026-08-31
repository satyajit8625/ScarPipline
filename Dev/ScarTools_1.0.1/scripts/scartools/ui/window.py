"""Common Maya-parented window base and lifecycle helpers."""

from __future__ import print_function

from .qt import QtCore, QtWidgets, apply_window_icon, maya_main_window
from .theme import apply as apply_theme
from ..framework.lifecycle import close_tool_windows, register_window


class BaseToolDialog(QtWidgets.QDialog):
    """Base for every top-level and child ScarTools dialog."""

    TOOL_ID = "scartools"

    def __init__(self, parent=None, tool_id=None):
        super(BaseToolDialog, self).__init__(
            parent if parent is not None else maya_main_window()
        )
        self._scartools_tool_id = str(tool_id or self.TOOL_ID)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        apply_window_icon(self)
        apply_theme(self)

        register_window(self._scartools_tool_id, self)

        # Enforce license for department tools (Modeling, Rigging, Skin, Texturing, Finalizer, Renamer)
        if self._scartools_tool_id != "scartools":
            from ..licensing import is_activated
            if not is_activated():
                self.hide()
                self.setEnabled(False)
                try:
                    from .license_dialog import show_license_dialog
                    show_license_dialog(parent=maya_main_window())
                except Exception:
                    pass
                self.close()
                self.deleteLater()
                raise RuntimeError("ScarTools Studio License Authentication Required.")




def close_windows(tool_id):
    return close_tool_windows(tool_id)


class AboutDialog(BaseToolDialog):
    """Clean About dialog displaying suite identity, version, and diagnostics."""

    OBJECT_NAME = "ScarToolsAboutDialog"
    TOOL_ID = "scartools"

    def __init__(self, parent=None):
        super(AboutDialog, self).__init__(
            parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle("About ScarTools")
        self.setMinimumSize(500, 440)
        self.resize(540, 480)
        self._build_ui()
        apply_theme(self)

    def _build_ui(self):
        from . import (
            CLOSE_BUTTON_WIDTH,
            configure_root_layout,
            create_brand_header,
            create_button,
            create_section_panel,
        )
        from ..diagnostics import collect
        from ..licensing import get_installed_license, get_machine_hardware_id

        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        header, _ = create_brand_header(
            "SCARTOOLS",
            "Production Pipeline Suite for Autodesk Maya",
            parent=self,
        )
        root.addWidget(header)

        # Suite Information Panel
        panel, layout, _ = create_section_panel(
            "Suite Information", accent="neutral", parent=self
        )

        info = collect()
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(7)

        rows = [
            ("Version", "v{}".format(info["version"])),
            ("Maya", str(info["maya_version"])),
            ("Python", str(info["python_version"])),
            ("Installed Tools", "{} registered".format(len(info["tools"]))),
            ("Package Root", str(info["package_root"])),
        ]

        for r_idx, (label, val) in enumerate(rows):
            lbl = QtWidgets.QLabel(label)
            lbl.setStyleSheet("color: #A0A0A0; font-weight: 500; font-size: 11px;")
            val_lbl = QtWidgets.QLabel(val)
            val_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            val_lbl.setWordWrap(True)
            val_lbl.setStyleSheet("color: #E0E0E0; font-size: 11px;")
            grid.addWidget(lbl, r_idx, 0)
            grid.addWidget(val_lbl, r_idx, 1)

        layout.addLayout(grid)
        root.addWidget(panel)

        # License & Authentication Panel
        lic_panel, lic_layout, _ = create_section_panel(
            "Studio License & Authentication", accent="operation", parent=self
        )
        lic_grid = QtWidgets.QGridLayout()
        lic_grid.setHorizontalSpacing(14)
        lic_grid.setVerticalSpacing(7)

        is_valid, msg, details = get_installed_license()
        user_name = details.get("user_id", "Not Authenticated") if is_valid else (details.get("user_id") or "Not Authenticated")
        expiry_info = details.get("expiry_date", "Unlicensed") if is_valid else "Unlicensed"
        hwid_str = details.get("hardware_id", get_machine_hardware_id())

        if is_valid:
            status_text = "✓ Active ({})".format(expiry_info)
            status_color = "#72D6AA"
        elif details.get("revoked") or "revoked" in msg.lower():
            status_text = "❌ Revoked by Studio Admin"
            status_color = "#E06C6C"
        else:
            status_text = "⚠️ Unlicensed / Not Activated"
            status_color = "#E06C6C"

        lic_rows = [
            ("Licensed Artist", user_name),
            ("Machine HWID", hwid_str),
            ("Seat Status", status_text),
        ]

        for r_idx, (label, val) in enumerate(lic_rows):
            lbl = QtWidgets.QLabel(label)
            lbl.setStyleSheet("color: #A0A0A0; font-weight: 500; font-size: 11px;")
            val_lbl = QtWidgets.QLabel(val)
            val_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            val_lbl.setWordWrap(True)
            val_color = status_color if label == "Seat Status" else "#E0E0E0"
            val_lbl.setStyleSheet("color: {}; font-weight: 600; font-size: 11px;".format(val_color))
            lic_grid.addWidget(lbl, r_idx, 0)
            lic_grid.addWidget(val_lbl, r_idx, 1)

        lic_layout.addLayout(lic_grid)
        root.addWidget(lic_panel)
        # 3. Studio Update Banner (if newer version available)
        from ..framework.updater import check_for_updates, apply_hot_update
        update_info = check_for_updates()
        if update_info.get("has_update"):
            banner = QtWidgets.QFrame(self)
            banner.setObjectName("ActionCard")
            banner.setStyleSheet("border-top: 2px solid #72D6AA; background: #202622;")
            b_layout = QtWidgets.QHBoxLayout(banner)
            b_layout.setContentsMargins(12, 8, 12, 8)
            b_lbl = QtWidgets.QLabel("⚡ ScarTools v{} is available on Share/".format(update_info.get("latest_version")), banner)
            b_lbl.setStyleSheet("color: #72D6AA; font-weight: 600; font-size: 11px;")
            self.btn_update = create_button("1-Click Update", role="primary", fixed_width=110, parent=banner)
            self.btn_update.clicked.connect(self._do_hot_update)
            b_layout.addWidget(b_lbl)
            b_layout.addStretch(1)
            b_layout.addWidget(self.btn_update)
            root.addWidget(banner)

        root.addStretch(1)

        footer = QtWidgets.QHBoxLayout()
        self.btn_check_update = create_button("Check Updates", role="secondary", parent=self)
        self.diag_button = create_button("View Diagnostics", role="secondary", parent=self)
        self.lic_button = create_button("Manage License...", role="secondary", parent=self)
        self.close_button = create_button(
            "Close", role="secondary", fixed_width=CLOSE_BUTTON_WIDTH, parent=self
        )
        footer.addWidget(self.btn_check_update)
        footer.addWidget(self.diag_button)
        footer.addWidget(self.lic_button)
        footer.addStretch(1)
        footer.addWidget(self.close_button)
        root.addLayout(footer)

        self.close_button.clicked.connect(self.close)
        self.diag_button.clicked.connect(self._show_diagnostics)
        self.lic_button.clicked.connect(self._show_licensing)
        self.btn_check_update.clicked.connect(self._check_updates_manual)

    def _check_updates_manual(self):
        from ..framework.updater import check_for_updates
        info = check_for_updates(force=True)
        if info.get("has_update"):
            QtWidgets.QMessageBox.information(
                self,
                "Update Available",
                "⚡ ScarTools v{} is available on Share/!\n\nClick '1-Click Update' to hot-reload.".format(info.get("latest_version"))
            )
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Up to Date",
                "✓ ScarTools v{} is currently the latest version.".format(info.get("current_version"))
            )

    def _do_hot_update(self):
        from ..framework.updater import apply_hot_update
        try:
            res = apply_hot_update()
            QtWidgets.QMessageBox.information(
                self,
                "Update Complete",
                "✓ ScarTools updated successfully to v{}!\n({} modules reloaded).".format(
                    res.get("version"), res.get("modules_reloaded")
                )
            )
            self.close()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Update Failed", "Could not apply update:\n{}".format(e))

    def _show_licensing(self):
        from .license_dialog import show_license_dialog
        from .qt import maya_main_window
        show_license_dialog(parent=maya_main_window())
        self.close()

    def _show_diagnostics(self):
        from .qt import maya_main_window
        diag = DiagnosticsDialog(parent=maya_main_window())
        diag.show()
        diag.raise_()
        diag.activateWindow()


class DiagnosticsDialog(BaseToolDialog):
    """Clean Diagnostics dialog displaying suite health and environment report."""

    OBJECT_NAME = "ScarToolsDiagnosticsDialog"
    TOOL_ID = "scartools"

    def __init__(self, parent=None):
        super(DiagnosticsDialog, self).__init__(
            parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle("ScarTools — Diagnostics Report")
        self.setMinimumSize(560, 480)
        self.resize(600, 520)
        self._build_ui()
        apply_theme(self)

    def _build_ui(self):
        from . import (
            CLOSE_BUTTON_WIDTH,
            configure_root_layout,
            create_brand_header,
            create_button,
            create_section_panel,
        )
        from ..diagnostics import format_report

        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        header, _ = create_brand_header(
            "DIAGNOSTICS",
            "System Environment & Suite Health Report",
            parent=self,
        )
        root.addWidget(header)

        panel, layout, _ = create_section_panel(
            "Diagnostic Output", accent="neutral", parent=self
        )

        self.box = QtWidgets.QPlainTextEdit(self)
        self.box.setReadOnly(True)
        self.box.setStyleSheet(
            "QPlainTextEdit {"
            "  background-color: #1A1D23;"
            "  color: #D4D4D4;"
            "  font-family: Consolas, 'Courier New', monospace;"
            "  font-size: 11px;"
            "  border: 1px solid #2D333F;"
            "  border-radius: 4px;"
            "  padding: 8px;"
            "}"
        )
        self.box.setPlainText(format_report())
        layout.addWidget(self.box)
        root.addWidget(panel, 1)

        footer = QtWidgets.QHBoxLayout()
        self.copy_btn = create_button("📋 Copy to Clipboard", role="secondary", parent=self)
        self.close_btn = create_button(
            "Close", role="secondary", fixed_width=CLOSE_BUTTON_WIDTH, parent=self
        )
        footer.addWidget(self.copy_btn)
        footer.addStretch(1)
        footer.addWidget(self.close_btn)
        root.addLayout(footer)

        self.close_btn.clicked.connect(self.close)
        self.copy_btn.clicked.connect(self._copy_to_clipboard)

    def _copy_to_clipboard(self):
        clipboard = QtWidgets.QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.box.toPlainText())
            self.copy_btn.setText("✓ Copied!")
            QtCore.QTimer.singleShot(2000, lambda: self.copy_btn.setText("📋 Copy to Clipboard"))


_about_dialog_instance = None


def show_about_dialog():
    global _about_dialog_instance
    try:
        if _about_dialog_instance is not None:
            _about_dialog_instance.close()
            _about_dialog_instance.deleteLater()
    except Exception:
        pass
    _about_dialog_instance = AboutDialog(parent=maya_main_window())
    _about_dialog_instance.show()
    _about_dialog_instance.raise_()
    _about_dialog_instance.activateWindow()
    return _about_dialog_instance


def show_diagnostics_dialog():
    diag = DiagnosticsDialog(parent=maya_main_window())
    diag.show()
    diag.raise_()
    diag.activateWindow()
    return diag


__all__ = [
    "BaseToolDialog",
    "AboutDialog",
    "DiagnosticsDialog",
    "show_about_dialog",
    "show_diagnostics_dialog",
    "close_windows",
]
