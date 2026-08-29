# -*- coding: utf-8 -*-
"""Studio License Activation and User Login Qt Dialog for ScarTools."""

from __future__ import absolute_import, division, print_function

import getpass
import os
import sys

import maya.cmds as cmds
try:
    import maya.OpenMayaUI as omui
except Exception:
    omui = None

try:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance

from .tokens import FORM_LABEL_WIDTH, FIELD_HEIGHT, INLINE_SPACING
from .window import BaseToolDialog, maya_main_window
from ..licensing import (
    get_machine_hardware_id,
    validate_license_key,
    save_license,
    get_installed_license,
    is_activated,
)


class LicenseActivationDialog(BaseToolDialog):
    """Standardized studio license authentication dialog for ScarTools."""

    OBJECT_NAME = "ScarToolsLicenseDialog"
    TOOL_ID = "scartools"

    def __init__(self, parent=None):
        super(LicenseActivationDialog, self).__init__(
            parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setWindowTitle("ScarTools — Studio Login & Activation")
        self.setObjectName(self.OBJECT_NAME)

        from . import configure_window, configure_root_layout
        configure_window(self, (540, 380), (620, 440))

        self._build_ui()
        self._prefill_credentials()

    def _build_ui(self):
        from . import (
            configure_root_layout,
            create_brand_header,
            create_section_panel,
            configure_field,
            create_button,
        )

        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Brand Header
        header, self.desc_lbl = create_brand_header(
            "STUDIO ACTIVATION",
            "Hardware-locked license authentication & artist login",
            parent=self,
        )
        root.addWidget(header)

        # 2. Form Card
        panel, panel_layout, _ = create_section_panel("License Credentials", accent="pipeline", parent=self)

        form = QtWidgets.QFormLayout()
        form.setContentsMargins(4, 4, 4, 4)
        form.setSpacing(10)
        form.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        # Machine HWID
        hwid_row = QtWidgets.QHBoxLayout()
        hwid_row.setSpacing(8)
        hwid_val = get_machine_hardware_id()
        self.hwid_display = QtWidgets.QLineEdit(hwid_val)
        self.hwid_display.setObjectName("LicenseHwidDisplay")
        self.hwid_display.setReadOnly(True)
        configure_field(self.hwid_display)

        self.copy_hwid_btn = create_button("📋 Copy HWID", role="secondary", fixed_width=110, parent=self)
        self.copy_hwid_btn.clicked.connect(self._copy_hwid)
        hwid_row.addWidget(self.hwid_display, 1)
        hwid_row.addWidget(self.copy_hwid_btn)

        hwid_lbl = QtWidgets.QLabel("Machine HWID")
        hwid_lbl.setFixedWidth(FORM_LABEL_WIDTH + 25)
        form.addRow(hwid_lbl, hwid_row)

        # Artist User ID
        self.user_input = QtWidgets.QLineEdit()
        self.user_input.setText(getpass.getuser())
        self.user_input.setPlaceholderText("e.g. john.doe or artist@studio.com")
        configure_field(self.user_input)

        user_lbl = QtWidgets.QLabel("Artist User ID")
        user_lbl.setFixedWidth(FORM_LABEL_WIDTH + 25)
        form.addRow(user_lbl, self.user_input)

        # License Key
        self.key_input = QtWidgets.QLineEdit()
        self.key_input.setPlaceholderText("SCAR-XXXX-XXXX-XXXXXXXX-XXXXXXXX")
        configure_field(self.key_input)

        key_lbl = QtWidgets.QLabel("License Key")
        key_lbl.setFixedWidth(FORM_LABEL_WIDTH + 25)
        form.addRow(key_lbl, self.key_input)

        panel_layout.addLayout(form)
        root.addWidget(panel)

        # Tip Note
        info_note = QtWidgets.QLabel(
            "💡 Tip: Click 'Copy HWID' and send it with your User ID to your Studio Administrator to receive your key."
        )
        info_note.setObjectName("InfoNote")
        info_note.setWordWrap(True)
        root.addWidget(info_note)

        # Status / Error Label
        self.error_label = QtWidgets.QLabel("")
        self.error_label.setObjectName("ErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setMinimumHeight(18)
        root.addWidget(self.error_label)

        # Action Buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(INLINE_SPACING)
        btn_row.addStretch(1)

        self.activate_btn = create_button("🚀 Activate License", role="primary", fixed_width=160, parent=self)
        self.activate_btn.clicked.connect(self._handle_activation)

        self.cancel_btn = create_button("Cancel", role="secondary", fixed_width=80, parent=self)
        self.cancel_btn.clicked.connect(self.reject)

        btn_row.addWidget(self.activate_btn)
        btn_row.addWidget(self.cancel_btn)
        root.addLayout(btn_row)

    def _prefill_credentials(self):
        has_lic, _, details = get_installed_license()
        if has_lic and details:
            self.user_input.setText(details.get("user_id", getpass.getuser()))
            self.key_input.setText(details.get("license_key", ""))
            self.error_label.setObjectName("SuccessLabel")
            self.error_label.setText("✓ Active License: {} ({})".format(details.get("user_id"), details.get("expiry_date")))

    def _copy_hwid(self):
        hwid_text = self.hwid_display.text().strip()
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(hwid_text)
        self.copy_hwid_btn.setText("✓ Copied!")
        QtCore.QTimer.singleShot(2000, lambda: self.copy_hwid_btn.setText("📋 Copy HWID"))

    def _handle_activation(self):
        user_id = self.user_input.text().strip()
        key = self.key_input.text().strip()

        try:
            import importlib
            from .. import licensing
            importlib.reload(licensing)
            validate_fn = licensing.validate_license_key
            save_fn = licensing.save_license
        except Exception:
            validate_fn = validate_license_key
            save_fn = save_license

        is_valid, msg, details = validate_fn(user_id, key, check_central=True, force_refresh=True)
        if not is_valid:
            self.error_label.setObjectName("ErrorLabel")
            self.error_label.setText("❌ " + msg)
            return

        try:
            save_fn(user_id, key)
            self.error_label.setObjectName("SuccessLabel")
            self.error_label.setText("✓ License activated successfully for {}!".format(details["user_id"]))
            QtWidgets.QApplication.processEvents()

            # Live reload menu & shelf in Maya
            try:
                from ..menu import register_menu
                register_menu()
            except Exception:
                pass

            try:
                from ..shelf import build_shelf
                build_shelf(rebuild=True)
            except Exception:
                pass

            self.accept()
        except Exception as exc:
            self.error_label.setObjectName("ErrorLabel")
            self.error_label.setText("❌ Error saving license: " + str(exc))


_license_dialog_instance = None


def show_license_dialog(parent=None):
    """Open or focus the Studio License Activation dialog."""
    global _license_dialog_instance
    try:
        if _license_dialog_instance:
            _license_dialog_instance.close()
            _license_dialog_instance.deleteLater()
    except Exception:
        pass
    _license_dialog_instance = LicenseActivationDialog(parent=parent or maya_main_window())
    _license_dialog_instance.show()
    _license_dialog_instance.raise_()
    _license_dialog_instance.activateWindow()
    return _license_dialog_instance


__all__ = ["LicenseActivationDialog", "show_license_dialog"]
