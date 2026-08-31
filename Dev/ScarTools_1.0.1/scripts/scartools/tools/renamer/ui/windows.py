# -*- coding: utf-8 -*-
"""Centralized Qt User Interface for Pipeline Renamer."""

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
    FORM_LABEL_WIDTH,
    INLINE_SPACING,
    apply_theme,
    configure_field,
    configure_root_layout,
    configure_window,
    create_action_footer,
    create_brand_header,
    create_section_panel,
    repolish,
)
from ..operations import (
    execute_batch_rename,
    get_selected_or_hierarchy,
)


class PipelineRenamerWindow(BaseToolDialog):
    """
    Modular batch node renamer built on the centralized ScarTools framework.

    Layout Structure:
    1. Shared Brand Header (create_brand_header)
    2. SectionPanel: Search and Replace (accent="pipeline")
    3. SectionPanel: Prefix & Suffix (accent="pipeline")
    4. SectionPanel: Numbering (accent="pipeline")
    5. SectionPanel: Rename from Scratch (accent="pipeline")
    6. Shared Action Footer (create_action_footer)
    """

    OBJECT_NAME = "ScarToolsPipelineRenamerWindow"
    TOOL_ID = "pipeline_renamer"

    def __init__(self, parent=None):
        super(PipelineRenamerWindow, self).__init__(
            parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle("Pipeline Renamer")
        apply_window_icon(self)
        configure_window(self, (620, 520), (680, 560))
        self._build_ui()
        self._connect()
        apply_theme(self)
        self._refresh_status()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Shared Brand Header ---------------------------------------
        header, self.header_subtitle = create_brand_header(
            "PIPELINE RENAMER",
            "Fast batch node renaming and department suffixing",
            parent=self,
        )
        root.addWidget(header)

        # 2. Section 1: Search and Replace -----------------------------
        sr_panel, sr_layout, _ = create_section_panel(
            "Search and Replace", accent="pipeline", parent=self
        )

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(8)
        search_lbl = QtWidgets.QLabel("Search")
        search_lbl.setFixedWidth(FORM_LABEL_WIDTH)
        self.sr_search_edit = QtWidgets.QLineEdit()
        configure_field(self.sr_search_edit)
        search_row.addWidget(search_lbl)
        search_row.addWidget(self.sr_search_edit, 1)
        sr_layout.addLayout(search_row)

        replace_row = QtWidgets.QHBoxLayout()
        replace_row.setSpacing(8)
        replace_lbl = QtWidgets.QLabel("Replace")
        replace_lbl.setFixedWidth(FORM_LABEL_WIDTH)
        self.sr_replace_edit = QtWidgets.QLineEdit()
        configure_field(self.sr_replace_edit)
        replace_row.addWidget(replace_lbl)
        replace_row.addWidget(self.sr_replace_edit, 1)
        sr_layout.addLayout(replace_row)

        root.addWidget(sr_panel)

        # 3. Section 2: Prefix & Suffix --------------------------------
        ps_panel, ps_layout, _ = create_section_panel(
            "Prefix & Suffix", accent="pipeline", parent=self
        )

        ps_row = QtWidgets.QHBoxLayout()
        ps_row.setSpacing(INLINE_SPACING)

        # Prefix
        p_lbl = QtWidgets.QLabel("Prefix")
        p_lbl.setFixedWidth(50)
        self.prefix_edit = QtWidgets.QLineEdit()
        configure_field(self.prefix_edit)
        ps_row.addWidget(p_lbl)
        ps_row.addWidget(self.prefix_edit, 1)

        # Suffix
        s_lbl = QtWidgets.QLabel("Suffix")
        s_lbl.setFixedWidth(50)
        self.suffix_edit = QtWidgets.QLineEdit()
        configure_field(self.suffix_edit)
        ps_row.addWidget(s_lbl)
        ps_row.addWidget(self.suffix_edit, 1)

        ps_layout.addLayout(ps_row)
        root.addWidget(ps_panel)

        # 4. Section 3: Numbering --------------------------------------
        num_panel, num_layout, _ = create_section_panel(
            "Numbering", accent="pipeline", parent=self
        )

        # Enable Numbering Checkbox
        self.num_enable_check = QtWidgets.QCheckBox("Enable Numbering")
        self.num_enable_check.setChecked(True)
        self.num_enable_check.setStyleSheet("color: #E2E8F0; font-size: 11px; font-weight: 600;")
        num_layout.addWidget(self.num_enable_check)

        num_row = QtWidgets.QHBoxLayout()
        num_row.setSpacing(INLINE_SPACING)

        # Start Index
        self.start_lbl = QtWidgets.QLabel("Start #")
        self.start_lbl.setFixedWidth(50)
        self.num_start_spin = QtWidgets.QSpinBox()
        self.num_start_spin.setRange(0, 99999)
        self.num_start_spin.setValue(1)
        configure_field(self.num_start_spin)
        num_row.addWidget(self.start_lbl)
        num_row.addWidget(self.num_start_spin, 1)

        # Padding
        self.pad_lbl = QtWidgets.QLabel("Padding")
        self.pad_lbl.setFixedWidth(50)
        self.pad_lbl.setToolTip("Number padding digits (1 = 1, 2 = 01, 3 = 001)")
        self.num_pad_spin = QtWidgets.QSpinBox()
        self.num_pad_spin.setRange(1, 6)
        self.num_pad_spin.setValue(2)
        configure_field(self.num_pad_spin)
        num_row.addWidget(self.pad_lbl)
        num_row.addWidget(self.num_pad_spin, 1)

        num_layout.addLayout(num_row)
        root.addWidget(num_panel)

        # 5. Section 4: Rename -----------------------------------------
        rename_panel, rename_layout, _ = create_section_panel(
            "Rename", accent="pipeline", parent=self
        )

        rename_row = QtWidgets.QHBoxLayout()
        rename_row.setSpacing(INLINE_SPACING)
        rename_lbl = QtWidgets.QLabel("Rename")
        rename_lbl.setFixedWidth(FORM_LABEL_WIDTH)
        self.rename_edit = QtWidgets.QLineEdit()
        self.rename_edit.setPlaceholderText("Optional base name overwrite (e.g. hero_prop)")
        configure_field(self.rename_edit)
        rename_row.addWidget(rename_lbl)
        rename_row.addWidget(self.rename_edit, 1)
        rename_layout.addLayout(rename_row)

        root.addWidget(rename_panel)
        root.addStretch(1)

        # 6. Shared Action Footer --------------------------------------
        (
            action_footer,
            self.warning_label,
            self.apply_button,
            self.status_dot,
            self.status_label,
            self.view_log_button,
            _status_layout,
        ) = create_action_footer(
            "APPLY RENAME",
            message="Configure rename options and apply to selected Maya nodes.",
            parent=self,
            include_log=False,
        )
        root.addWidget(action_footer)

    def _connect(self):
        self.apply_button.clicked.connect(self._do_apply_rename)
        self.num_enable_check.toggled.connect(self._on_numbering_toggled)

    def _on_numbering_toggled(self, enabled):
        self.start_lbl.setEnabled(enabled)
        self.num_start_spin.setEnabled(enabled)
        self.pad_lbl.setEnabled(enabled)
        self.num_pad_spin.setEnabled(enabled)

    def _set_status(self, text, state="idle"):
        self.status_label.setText(str(text))
        self.status_label.setProperty("state", state)
        self.status_dot.setProperty("state", state)
        repolish(self.status_label)
        repolish(self.status_dot)

    def _set_message(self, text, state="neutral"):
        self.warning_label.setText(str(text))
        self.warning_label.setProperty("state", state)
        repolish(self.warning_label)

    def _refresh_status(self):
        try:
            nodes = cmds.ls(selection=True, long=True) or []
            count = len(nodes)
            if count > 0:
                self._set_status("Ready ({} node(s) selected)".format(count), "idle")
                self._set_message("Ready to rename {} selected node(s).".format(count), "neutral")
            else:
                self._set_status("Ready (0 selected)", "idle")
                self._set_message("Select Maya nodes to batch rename.", "neutral")
        except Exception:
            self._set_status("Ready", "idle")

    def _get_target_nodes(self):
        nodes = get_selected_or_hierarchy(hierarchy=False)
        if not nodes:
            self._set_status("No Maya nodes selected", "warning")
            self._set_message("Please select one or more Maya nodes first.", "warning")
            return []
        return nodes

    def _do_apply_rename(self):
        nodes = self._get_target_nodes()
        if not nodes:
            return

        search_str = self.sr_search_edit.text()
        replace_str = self.sr_replace_edit.text()
        prefix = self.prefix_edit.text()
        suffix = self.suffix_edit.text()
        base_name = self.rename_edit.text().strip()
        scratch_mode = bool(base_name)
        enable_numbering = self.num_enable_check.isChecked()
        start_idx = self.num_start_spin.value()
        padding = self.num_pad_spin.value()

        # Check if there is anything to do
        has_operations = (
            bool(search_str)
            or bool(prefix)
            or bool(suffix)
            or bool(base_name)
            or enable_numbering
        )

        if not has_operations:
            self._set_status("Please specify a rename operation", "warning")
            self._set_message("No transformation specified in Search, Prefix/Suffix, or Rename.", "warning")
            return

        self._set_status("Executing Batch Rename...", "running")
        self._set_message("Renaming {} node(s)...".format(len(nodes)), "neutral")
        QtWidgets.QApplication.processEvents()

        opts = {
            "search": search_str,
            "replace": replace_str,
            "case_sensitive": True,
            "use_regex": False,
            "prefix": prefix,
            "suffix": suffix,
            "rename_from_scratch": scratch_mode,
            "base_name": base_name,
            "mode": "Numbering",
            "start_idx": start_idx,
            "padding": padding,
            "apply_numbering": enable_numbering,
        }

        try:
            count = execute_batch_rename(nodes, "unified", opts)
            if count > 0:
                self._set_status("✓ Renamed {} node(s)".format(count), "success")
                self._set_message("✓ Successfully renamed {} node(s) in 1 Maya undo step (Ctrl+Z).".format(count), "success")
            else:
                self._set_status("No nodes changed", "idle")
                self._set_message("Executed: Node names remained unchanged.", "neutral")
        except Exception as exc:
            self._set_status("Error: " + str(exc), "error")
            self._set_message("Rename failed: " + str(exc), "error")


# ---------------------------------------------------------------------------
# Singleton & Public Launchers
# ---------------------------------------------------------------------------

_tool_instance = None


def show_ui():
    """Open or focus the Pipeline Renamer tool window."""
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

    _tool_instance = PipelineRenamerWindow(parent=maya_main_window())
    _tool_instance.show()
    _tool_instance.raise_()
    _tool_instance.activateWindow()
    return _tool_instance


def close_all_windows():
    """Close any open Pipeline Renamer windows."""
    global _tool_instance
    if _tool_instance:
        try:
            _tool_instance.close()
            _tool_instance.deleteLater()
        except Exception:
            pass
        _tool_instance = None
    return True


__all__ = ["PipelineRenamerWindow", "close_all_windows", "show_ui"]

