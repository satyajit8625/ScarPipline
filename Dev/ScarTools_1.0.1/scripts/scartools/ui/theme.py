# -*- coding: utf-8 -*-
"""Reusable ScarTools centralized dark UI theme for Maya/PySide windows."""

from __future__ import absolute_import, division, print_function

from ..framework.paths import resolve_icon
from .tokens import (
    FONT_FAMILY_BASE,
    FONT_FAMILY_MONO,
    COLOR_BG_ROOT,
    COLOR_BG_PANEL,
    COLOR_BG_DARK,
    COLOR_BG_INPUT,
    COLOR_BG_INPUT_FOCUS,
    COLOR_BG_INPUT_READONLY,
    COLOR_BORDER_DEFAULT,
    COLOR_BORDER_INPUT,
    COLOR_BORDER_FOCUS,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_LABEL,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_DISABLED,
    COLOR_PRIMARY_BLUE,
    COLOR_PRIMARY_BLUE_HOVER,
    COLOR_PRIMARY_BLUE_BORDER,
    COLOR_ACTION_BTN,
    COLOR_ACTION_BTN_HOVER,
    COLOR_ACTION_BTN_BORDER,
    COLOR_ACTION_BTN_PRESSED,
    COLOR_PRESET_BTN,
    COLOR_PRESET_BTN_HOVER,
    COLOR_PRESET_BTN_BORDER,
    COLOR_PRESET_BTN_TEXT,
    COLOR_ACCENT_MODELING,
    COLOR_ACCENT_RIGGING,
    COLOR_ACCENT_TEXTURING,
    COLOR_ACCENT_PIPELINE,
    COLOR_ACCENT_CLEANUP,
    COLOR_ACCENT_MIRROR,
    COLOR_ACCENT_COPY,
    COLOR_ACCENT_CLUSTER,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    COLOR_STATUS_ERROR,
    COLOR_STATUS_INFO,
    COLOR_STATUS_IDLE,
)

COLORS = {
    "background": COLOR_BG_ROOT,
    "surface": COLOR_BG_PANEL,
    "surface_dark": COLOR_BG_DARK,
    "border": COLOR_BORDER_DEFAULT,
    "border_active": COLOR_ACCENT_RIGGING,
    "text": COLOR_TEXT_SECONDARY,
    "muted": COLOR_TEXT_MUTED,
    "purple": "#665A82",
    "purple_hover": "#746594",
    "blue": COLOR_PRIMARY_BLUE,
    "blue_hover": COLOR_PRIMARY_BLUE_HOVER,
    "success": COLOR_STATUS_SUCCESS,
    "warning": COLOR_STATUS_WARNING,
    "danger": COLOR_STATUS_ERROR,
}

QSS = r'''
QDialog, QWidget#ScarToolsPage {
    background: #242424;
    color: #D8D8D8;
    font-family: "Segoe UI", "Arial";
    font-size: 12px;
}
QLabel { color: #D0D0D0; }
QLabel#Title { color: #F3F3F3; font-size: 17px; font-weight: 600; }
QLabel#Subtitle { color: #AFAFAF; font-size: 11px; }
QLabel#Muted { color: #AFAFAF; font-size: 11px; }
QLabel#Status[state="ready"] { color: #AFAFAF; }
QLabel#Status[state="idle"] { color: #C7C7C7; }
QLabel#Status[state="running"] { color: #79A9E6; }
QLabel#Status[state="success"] { color: #72D6AA; }
QLabel#Status[state="warning"] { color: #D6B36A; }
QLabel#Status[state="error"] { color: #E06C6C; }
QLabel#StatusDot { color: #8A8A8A; font-size: 18px; font-weight: 700; min-width: 20px; }
QLabel#StatusDot[state="running"] { color: #5C87C8; }
QLabel#StatusDot[state="success"] { color: #72D6AA; }
QLabel#StatusDot[state="warning"] { color: #D6B36A; }
QLabel#StatusDot[state="error"] { color: #E06C6C; }
QLabel#CountBadge {
    color: #C8C8C8; background: #202020; border: 1px solid #3B3B3B;
    border-radius: 4px; padding: 3px 7px;
}
QLabel#Warning { color: #B8B8B8; font-size: 11px; }
QLabel#Warning[state="success"] { color: #72D6AA; }
QLabel#Warning[state="positive"] { color: #72D6AA; }
QLabel#Warning[state="warning"] { color: #D6B36A; }
QLabel#Warning[state="caution"] { color: #D6B36A; }
QLabel#Warning[state="error"] { color: #E06C6C; }
QLabel#Warning[state="neutral"] { color: #B8B8B8; }
QLabel#PopupTitle, QLabel#LogDialogTitle { color: #F3F3F3; font-size: 15px; font-weight: 600; }
QLabel#PopupCurrent { color: #E0E0E0; }
QLabel#PopupCount { color: #BEBEBE; font-size: 11px; }
QLabel#PopupStatus { color: #C7C7C7; font-weight: 500; }
QLabel#PopupStatusDot { color: #5C87C8; font-size: 18px; font-weight: 700; }
QLabel#PopupStatusDot[state="running"] { color: #5C87C8; }
QLabel#PopupStatusDot[state="success"] { color: #72D6AA; }
QLabel#PopupStatusDot[state="warning"] { color: #D6B36A; }
QLabel#PopupStatusDot[state="error"] { color: #E06C6C; }
QFrame#Header {
    background: #292929; border: 1px solid #3A3A3A; border-radius: 6px;
}
QLabel#BrandHeaderLogo {
    background: #202020; border: 1px solid #3B3B3B; border-radius: 6px;
}
QFrame#ActionCard {
    background: #292929; border: 1px solid #3A3A3A; border-radius: 7px;
}
QFrame#ActionCard[accent="cleanup"] { border-top: 2px solid #A67C45; }
QFrame#ActionCard[accent="mirror"] { border-top: 2px solid #766A8E; }
QFrame#ActionCard[accent="copy"] { border-top: 2px solid #5684BD; }
QFrame#ActionCard[accent="cluster"] { border-top: 2px solid #4E937B; }
QFrame#SectionPanel {
    background: #292929; border: 1px solid #3A3A3A; border-radius: 6px;
}
QFrame#SectionPanel[accent="operation"],
QFrame#SectionPanel[accent="rig"] { border-top: 2px solid #5F7FA8; }
QFrame#SectionPanel[accent="data"],
QFrame#SectionPanel[accent="validation"] { border-top: 2px solid #667A70; }
QFrame#SectionPanel[accent="mirror"] { border-top: 2px solid #766A8E; }
QFrame#SectionPanel[accent="neutral"] { border-top: 2px solid #505050; }
QFrame#SectionPanel[accent="pipeline"] { border-top: 2px solid #4E937B; }
QFrame#SectionPanel[accent="texturing"] { border-top: 2px solid #A67C45; }
QLabel#SectionTitle {
    color: #D2D2D2; font-size: 11px; font-weight: 600; padding: 0;
}
QFrame#ActionFooter {
    background: #292929; border: 1px solid #3A3A3A; border-radius: 6px;
}
QLabel#ActionCardIcon {
    background: #202020; border: 1px solid #3B3B3B; border-radius: 6px;
}
QLabel#ActionCardTitle { color: #F0F0F0; font-size: 13px; font-weight: 600; }
QLabel#ActionCardDescription { color: #C5C5C5; font-size: 11px; }
QGroupBox {
    background: #292929; border: 1px solid #3A3A3A; border-radius: 6px;
    margin-top: 10px; padding-top: 9px; color: #C8C8C8;
    font-size: 11px; font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 10px; padding: 1px 6px;
    color: #A8A8A8; background: #242424;
}
QGroupBox#OperationGroup { border-top: 2px solid #5F7FA8; }
QGroupBox#MeshesGroup { border-top: 2px solid #667A70; }
QLineEdit {
    background: #181818;
    color: #FFFFFF;
    border: 1px solid #484848;
    border-radius: 5px;
    padding: 6px 10px;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 13px;
    font-weight: 600;
    min-height: 22px;
    selection-background-color: #665A82;
    selection-color: #FFFFFF;
}
QLineEdit:focus {
    border: 1px solid #9A89BB;
    background: #1E1E1E;
    color: #FFFFFF;
}
QLineEdit[readOnly="true"] {
    background: #141414;
    color: #CFC7DE;
    font-family: Consolas, "Courier New", monospace;
    font-weight: 700;
}
QPlainTextEdit, QTextEdit, QListWidget, QTableWidget {
    background: #202020; color: #D7D7D7; border: 1px solid #3B3B3B;
    border-radius: 4px; selection-background-color: #454055;
    selection-color: #FFFFFF;
}

QComboBox {
    background: #181818;
    border: 1px solid #484848;
    border-radius: 5px;
    padding: 5px 9px;
    color: #FFFFFF;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 12px;
    font-weight: 500;
    min-height: 20px;
}
QComboBox:hover { border-color: #5A5A5A; }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    background: #23272F;
    border-left: 1px solid #363C46;
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}
QComboBox::drop-down:hover {
    background: #2E3440;
    border-left-color: #4C566A;
}
QComboBox::down-arrow {
    image: url("__ARROW_DOWN__");
    width: 12px;
    height: 12px;
}
QComboBox::down-arrow:hover {
    image: url("__ARROW_DOWN_HOVER__");
}
QComboBox QAbstractItemView {
    background: #252525; color: #E0E0E0; border: 1px solid #464646;
    selection-background-color: #4F78B8; selection-color: #FFFFFF;
}

QSpinBox, QDoubleSpinBox {
    background: #181818;
    color: #FFFFFF;
    border: 1px solid #484848;
    border-radius: 5px;
    padding: 5px 8px;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 12px;
    font-weight: 500;
    min-height: 20px;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #83A6DA;
    background: #1E1E1E;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid #363C46;
    border-bottom: 1px solid #363C46;
    background: #23272F;
    border-top-right-radius: 4px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
    background: #2E3440;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid #363C46;
    background: #23272F;
    border-bottom-right-radius: 4px;
}
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: #2E3440;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url("__ARROW_UP__");
    width: 10px;
    height: 10px;
}
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover {
    image: url("__ARROW_UP_HOVER__");
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url("__ARROW_DOWN__");
    width: 10px;
    height: 10px;
}
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover {
    image: url("__ARROW_DOWN_HOVER__");
}

/* Centralized QSlider Theme */
QSlider::groove:horizontal {
    height: 4px;
    background: #2D3139;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #4F78B8;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #FFFFFF;
    border: 2px solid #4F78B8;
    width: 14px;
    height: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #E0E7FF;
    border-color: #6E94CE;
}
QSlider::handle:horizontal:disabled {
    background: #555555;
    border-color: #3A3A3A;
}

QPlainTextEdit, QTextEdit#ColorLogView {
    font-family: Consolas, "Courier New"; font-size: 10px;
}
QListWidget::item { padding: 5px 8px; }
QListWidget::item:hover { background: #2D2D2D; }
QHeaderView::section {
    background: #2A2A2A; color: #AFAFAF; border: none;
    border-right: 1px solid #363636; border-bottom: 1px solid #3B3B3B;
    padding: 6px 8px; font-size: 10px; font-weight: 600;
}
QPushButton {
    background: #343434; border: 1px solid #484848; border-radius: 5px;
    padding: 7px 14px; color: #D5D5D5; font-weight: 600;
}
QPushButton:hover { background: #3C3C3C; border-color: #5A5A5A; }
QPushButton:pressed { background: #2D2D2D; }
QPushButton:focus, QComboBox:focus, QLineEdit:focus, QSpinBox:focus {
    border: 1px solid #83A6DA;
}
QPushButton:disabled { background: #2A2A2A; color: #666; border-color: #333; }
QPushButton#PrimaryButton, QPushButton[role="primary"] {
    background: #4F78B8; border: 1px solid #6E94CE; color: white;
    padding: 0 14px; font-size: 12px; font-weight: 700;
}
QPushButton#PrimaryButton:hover, QPushButton[role="primary"]:hover {
    background: #5C87C8; border-color: #83A6DA;
}
QPushButton#PrimaryButton[mode="export"] { background: #4F78B5; border-color: #7095CF; }
QPushButton#PrimaryButton[mode="import"] { background: #4C9278; border-color: #70B69A; }
QPushButton#PrimaryButton[mode="import"]:hover { background: #59A587; border-color: #83C5A9; }
QPushButton#ViewLogButton, QPushButton[role="log"] {
    background: #2E2E2E; color: #D0D0D0; padding: 5px 12px;
}
QPushButton#TableSelectBtn {
    background: #363636; border: 1px solid #4E4E4E; border-radius: 4px;
    color: #D5D5D5; font-size: 11px; font-weight: 600; padding: 0 8px; margin: 0; min-height: 22px;
}
QPushButton#TableSelectBtn:hover {
    background: #444444; border-color: #646464; color: #FFFFFF;
}
QPushButton#TableSelectBtn:pressed {
    background: #282828;
}
QPushButton#TableFixBtn {
    background: #4F78B8; border: 1px solid #6E94CE; border-radius: 4px;
    color: #FFFFFF; font-size: 11px; font-weight: 700; padding: 0 8px; margin: 0; min-height: 22px;
}
QPushButton#TableFixBtn:hover {
    background: #5C87C8; border-color: #83A6DA;
}
QPushButton#TableFixBtn:pressed {
    background: #3D6095;
}
QPushButton#ActionCardButton {
    color: #FFFFFF; border-radius: 5px; padding: 0 16px;
    font-size: 11px; font-weight: 700;
}
QPushButton#ActionCardButton[accent="cleanup"] {
    background: #9A6A32; border: 1px solid #C18B4A;
}
QPushButton#ActionCardButton[accent="cleanup"]:hover {
    background: #AD783A; border-color: #D29A57;
}
QPushButton#ActionCardButton[accent="mirror"] {
    background: #665A82; border: 1px solid #887AA7;
}
QPushButton#ActionCardButton[accent="mirror"]:hover {
    background: #746594; border-color: #9A89BB;
}
QPushButton#ActionCardButton[accent="copy"] {
    background: #496F9F; border: 1px solid #6D96C8;
}
QPushButton#ActionCardButton[accent="copy"]:hover {
    background: #5680B5; border-color: #82A9D8;
}
QPushButton#ActionCardButton[accent="cluster"] {
    background: #477B69; border: 1px solid #69A28E;
}
QPushButton#ActionCardButton[accent="cluster"]:hover {
    background: #528D78; border-color: #7AB49F;
}
QPushButton#DangerButton, QPushButton[role="danger"] {
    background: #3B3032; border-color: #67484D; color: #D7BFC3;
}
QPushButton#DangerButton:hover, QPushButton[role="danger"]:hover {
    background: #49373A; border-color: #8A5A62; color: #F0D8DC;
}

QPushButton[role="action"] {
    background: #3A4759;
    border: 1px solid #5A6E8A;
    border-radius: 4px;
    color: #FFFFFF;
    font-size: 11px;
    font-weight: 700;
    padding: 0 10px;
}
QPushButton[role="action"]:hover {
    background: #48586E;
    border-color: #728AB0;
    color: #FFFFFF;
}
QPushButton[role="action"]:pressed {
    background: #2D3745;
}

QPushButton[role="preset"] {
    background: #30333A;
    border: 1px solid #484D58;
    border-radius: 4px;
    color: #DDE2EC;
    font-size: 11px;
    font-weight: 700;
    font-family: Consolas, "Courier New", monospace;
    padding: 0 6px;
}
QPushButton[role="preset"]:hover {
    background: #404552;
    border-color: #68758C;
    color: #FFFFFF;
}
QPushButton[role="preset"]:pressed {
    background: #25282E;
}

QFrame#StatusBar { background: transparent; border: 0; }
QLabel#ApiBadge {
    color: #B8ACD0; background: #2B2832; border: 1px solid #4A4258;
    border-radius: 4px; padding: 3px 7px; font-size: 10px; font-weight: 600;
}
QGroupBox#MirrorSettingsGroup { border-top: 2px solid #766A8E; }
QPushButton#MirrorPrimaryButton {
    background: #665A82; border: 1px solid #887AA7; color: #FFFFFF;
    border-radius: 5px; font-size: 12px; font-weight: 700;
}
QPushButton#MirrorPrimaryButton:hover {
    background: #746594; border-color: #9A89BB;
}
QTabWidget::pane { border: 1px solid #3A3A3A; background: #242424; }
QTabBar::tab {
    background: #303030; color: #BDBDBD; border: 1px solid #444;
    padding: 8px 24px; min-width: 120px;
}
QTabBar::tab:selected { background: #454545; color: #FFF; border-top: 2px solid #766A8E; }
QTabWidget#MainTabs::pane { border: 0; background: #242424; top: 0; }
QTabWidget#MainTabs QTabBar { background: #242424; }
QTabWidget#MainTabs QTabBar::tab {
    background: #303030; color: #BDBDBD; border: 1px solid #444444;
    border-bottom: 1px solid #3A3A3A; padding: 8px 20px;
    min-width: 0; font-size: 11px; font-weight: 500;
}
QTabWidget#MainTabs QTabBar::tab:hover {
    background: #383838; color: #E0E0E0;
}
QTabWidget#MainTabs QTabBar::tab:selected {
    background: #414141; color: #FFFFFF; border-color: #555555;
    border-bottom-color: #414141; border-top: 2px solid #766A8E;
    font-weight: 600;
}
QTableWidget#MeshTable, QTableWidget {
    background: #202020; alternate-background-color: #242424;
    border: 1px solid #3B3B3B; border-radius: 4px; gridline-color: #303030;
    color: #D7D7D7; outline: none; selection-background-color: #3B3B3B;
    selection-color: #FFFFFF;
}
QTableWidget::item { padding: 5px 8px; border: none; }
QCheckBox {
    color: #E2E2E2;
    spacing: 8px;
    font-size: 11px;
    font-weight: 500;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    background: #181818;
    border: 1px solid #525252;
    border-radius: 3px;
}
QCheckBox::indicator:hover {
    background: #242424;
    border-color: #79A9E6;
}
QCheckBox::indicator:checked {
    background: #4F78B8;
    border-color: #7097D1;
    image: url("__CHECKBOX_CHECKED__");
}
QCheckBox::indicator:checked:hover {
    background: #5C87C8;
    border-color: #8BB0E8;
    image: url("__CHECKBOX_CHECKED__");
}
QProgressBar {
    background: #202020; border: 1px solid #3B3B3B; border-radius: 4px;
    color: #D8D8D8; text-align: center; min-height: 16px;
}
QProgressBar::chunk { background: #665A82; border-radius: 3px; }
QScrollBar:vertical { background: #242424; width: 10px; margin: 1px; }
QScrollBar::handle:vertical { background: #4A4A4A; min-height: 24px; border-radius: 4px; }
QScrollBar:add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMenu {
    background-color: #242424;
    color: #DCDCDC;
    border: 1px solid #3E3E3E;
    border-radius: 6px;
    padding: 4px;
    font-size: 11px;
    font-weight: 500;
}
QMenu::item {
    background: transparent;
    padding: 6px 20px 6px 12px;
    border-radius: 4px;
    margin: 1px 2px;
}
QMenu::item:selected {
    background-color: #4F78B8;
    color: #FFFFFF;
}
QMenu::item:disabled {
    color: #666666;
}
QMenu::separator {
    height: 1px;
    background: #383838;
    margin: 4px 6px;
}

/* Centralized Installer & Setup Components */
QLabel#SetupTitle { color: #FFFFFF; font-size: 17px; font-weight: 600; }
QLabel#SetupSubtitle { color: #999999; font-size: 11px; }
QLabel#SetupLogo { background: #202020; border: 1px solid #3B3B3B; border-radius: 7px; }
QLabel#VersionBadge {
    color: #D8D1E8; background: #322D3B; border: 1px solid #665A82;
    border-radius: 10px; padding: 4px 10px; font-size: 11px; font-weight: 700;
}
QFrame#StatusCard {
    background: #292929; border: 1px solid #3A3A3A; border-top: 2px solid #766A8E;
    border-radius: 6px;
}
QLabel#Caption { color: #888888; font-size: 9px; font-weight: 700; }
QLabel#StatusPill {
    color: #CFC7DE; background: #2B2832; border: 1px solid #4A4258;
    border-radius: 4px; padding: 4px 8px; font-size: 10px; font-weight: 700;
}
QPushButton#LicenseBtn {
    background: #4F78B8; border: 1px solid #6E94CE; color: #FFFFFF;
    border-radius: 5px; font-size: 11px; font-weight: 700; min-height: 24px;
}
QPushButton#LicenseBtn:hover { background: #5C87C8; }
QPushButton#SettingsBtn {
    background: #333333; border: 1px solid #4A4A4A; color: #E0E0E0;
    border-radius: 5px; font-size: 11px; font-weight: 600; min-height: 24px;
}
QPushButton#SettingsBtn:hover { background: #404040; color: #FFFFFF; }
QLabel#Compatibility { color: #A79DBD; font-size: 10px; font-weight: 600; }

/* Centralized License Activation Dialog Components */
QFrame#HeaderFrame { background: #292929; border: 1px solid #3A3A3A; border-radius: 6px; }
QLabel#DialogTitle { color: #FFFFFF; font-size: 16px; font-weight: 700; }
QLabel#DialogDesc { color: #B5B5B5; font-size: 12px; }
QFrame#FormCard {
    background: #292929; border: 1px solid #3A3A3A; border-top: 2px solid #766A8E;
    border-radius: 6px;
}
QLabel#InfoNote { color: #9E9E9E; font-size: 11px; }
QLabel#ErrorLabel { color: #E06C6C; font-weight: 600; font-size: 12px; min-height: 20px; }
QPushButton#SecondaryButton {
    background: #2E2E2E; border: 1px solid #4A4258; color: #D8D1E8; font-weight: 600;
}
QPushButton#SecondaryButton:hover { background: #3B3347; border-color: #665A82; color: #FFFFFF; }
QPushButton#CancelButton { background: #343434; border: 1px solid #484848; color: #D5D5D5; }

/* Centralized Vector3 Axis Badges */
QLabel#AxisBadgeX {
    background: #A63434; color: #FFFFFF; font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 3px;
}
QLabel#AxisBadgeY {
    background: #3B7D44; color: #FFFFFF; font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 3px;
}
QLabel#AxisBadgeZ {
    background: #3B5F9E; color: #FFFFFF; font-weight: 700; font-size: 10px; padding: 2px 6px; border-radius: 3px;
}

/* Centralized Tag Input Components */
QFrame#TagChip {
    background: #2D323B; border: 1px solid #4C566A; border-radius: 3px; padding: 1px 4px;
}
QLabel#TagLabel {
    color: #D8DEE9; font-size: 10.5px; font-weight: 600;
}
QToolButton#TagRemoveBtn {
    border: none; color: #9CA3AF; font-size: 12px; font-weight: 700;
}
QToolButton#TagRemoveBtn:hover {
    color: #E06C6C;
}

/* Centralized Pipeline Step Wizard */
QToolButton#WizardStepBtn {
    background-color: #1F2228; color: #8A94A6; border: 1px solid #363C46;
    border-radius: 4px; font-weight: 500; font-size: 11px; padding: 2px 8px;
}
QToolButton#WizardStepBtn[state="active"] {
    background-color: #4F78B8; color: #FFFFFF; border: 1px solid #7097D1; font-weight: 700;
}
QToolButton#WizardStepBtn[state="done"] {
    background-color: #23382D; color: #72D6AA; border: 1px solid #3E6B56; font-weight: 600;
}

/* Centralized Preset Bar Action Buttons */
QToolButton#PresetActionBtn {
    background-color: #26292E; color: #D8DEE9; border: 1px solid #3A404D;
    border-radius: 4px; font-size: 11px; font-weight: 600; padding: 2px 6px;
}
QToolButton#PresetActionBtn:hover {
    background-color: #353B47; color: #FFFFFF; border-color: #555E6F;
}

/* Centralized Log Viewer & Console Components */
QLabel#LogCountBadge {
    background-color: #23272F; color: #9CA3AF; border: 1px solid #363C46;
    border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 600;
}
QPlainTextEdit#ConsoleView {
    background-color: #16181D; color: #D8DEE9; border: 1px solid #2B303C;
    border-radius: 4px; padding: 6px; font-family: Consolas, monospace; font-size: 11px;
}

/* Centralized Labeled Slider Typography */
QLabel#SliderTitle {
    color: #E2E8F0; font-weight: 500; font-size: 11.5px;
}
QLabel#SliderValue {
    color: #79A9E6; font-weight: 700; font-family: Consolas, monospace; font-size: 11.5px;
}

/* Centralized Transparent Scroll Area */
QScrollArea#TransparentScrollArea {
    border: none; background: transparent;
}
QScrollArea#TransparentScrollArea > QWidget > QWidget {
    background: transparent;
}
QLabel#LicenseHwidDisplay {
    font-family: Consolas, monospace; font-weight: 700; color: #DCE3EE;
}
QLabel#SuccessLabel {
    color: #72D6AA; font-weight: 600; font-size: 11.5px;
}
'''


def _theme_icons():
    down = (resolve_icon("arrow_down.png") or "").replace("\\", "/")
    up = (resolve_icon("arrow_up.png") or "").replace("\\", "/")
    down_h = (resolve_icon("arrow_down_hover.png") or "").replace("\\", "/")
    up_h = (resolve_icon("arrow_up_hover.png") or "").replace("\\", "/")
    chk = (resolve_icon("checkbox_checked.png") or "").replace("\\", "/")
    return {
        "arrow_down": down,
        "arrow_up": up,
        "arrow_down_hover": down_h,
        "arrow_up_hover": up_h,
        "checkbox_checked": chk,
    }


_CURRENT_THEME = "dark_studio"

THEMES = {
    "dark_studio": {
        "name": "Dark Studio (Default)",
        "bg_root": "#1E1E1E",
        "bg_panel": "#292929",
        "primary_blue": "#4F78B8",
    },
    "cyber_obsidian": {
        "name": "Cyber Obsidian",
        "bg_root": "#0C0D11",
        "bg_panel": "#151820",
        "primary_blue": "#00C2E0",
    },
    "slate_blue": {
        "name": "Slate Blue (Unreal Style)",
        "bg_root": "#161920",
        "bg_panel": "#202530",
        "primary_blue": "#5F7FA8",
    },
    "maya_match": {
        "name": "Maya Native Match",
        "bg_root": "#2B2B2B",
        "bg_panel": "#333333",
        "primary_blue": "#5275A1",
    },
}


def get_available_themes():
    """Return dictionary of available theme identifier keys and display names."""
    return {k: v["name"] for k, v in THEMES.items()}


def get_active_theme():
    """Return current active theme identifier key."""
    return _CURRENT_THEME


def set_active_theme(theme_name):
    """Set the active theme identifier."""
    global _CURRENT_THEME
    if theme_name in THEMES:
        _CURRENT_THEME = theme_name


def get_theme_stylesheet(theme_name=None):
    """Return fully-rendered QSS with localized icon URLs and theme color overrides."""
    t_name = theme_name or _CURRENT_THEME
    t_data = THEMES.get(t_name, THEMES["dark_studio"])

    icons = _theme_icons()
    qss = QSS
    for k, v in icons.items():
        qss = qss.replace("__" + k.upper() + "__", v)

    # Apply palette overrides
    if t_name != "dark_studio":
        qss = qss.replace("#1E1E1E", t_data["bg_root"])
        qss = qss.replace("#292929", t_data["bg_panel"])
        qss = qss.replace("#4F78B8", t_data["primary_blue"])

    return qss


def apply(widget, theme_name=None):
    """Apply the centralized dark theme to a Qt widget."""
    widget.setStyleSheet(get_theme_stylesheet(theme_name=theme_name))
    return widget


def repolish(widget):
    """Force Qt to re-evaluate dynamic property style rules on a widget."""
    if widget is None:
        return
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


__all__ = [
    "COLORS",
    "THEMES",
    "QSS",
    "apply",
    "repolish",
    "get_theme_stylesheet",
    "get_available_themes",
    "get_active_theme",
    "set_active_theme",
]
