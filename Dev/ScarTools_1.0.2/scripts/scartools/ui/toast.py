# -*- coding: utf-8 -*-
"""Sleek, animated Viewport HUD Toast Notifications for Maya."""

from __future__ import absolute_import, division, print_function

from .qt import QtCore, QtGui, QtWidgets, maya_main_window
from .tokens import (
    COLOR_BG_PANEL,
    COLOR_BORDER_DEFAULT,
    COLOR_STATUS_ERROR,
    COLOR_STATUS_INFO,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    FONT_FAMILY_BASE,
)


class ToastWidget(QtWidgets.QFrame):
    """Semi-transparent floating notification overlay inside Maya."""

    def __init__(self, message, level="info", parent=None):
        super(ToastWidget, self).__init__(parent or maya_main_window())
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.ToolTip)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        color_map = {
            "success": (COLOR_STATUS_SUCCESS, "✓"),
            "warning": (COLOR_STATUS_WARNING, "⚠"),
            "error": (COLOR_STATUS_ERROR, "✕"),
            "info": (COLOR_STATUS_INFO, "ℹ"),
        }
        accent, icon_char = color_map.get(str(level).lower(), (COLOR_STATUS_INFO, "ℹ"))

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 16, 10)
        layout.setSpacing(10)

        icon_lbl = QtWidgets.QLabel(icon_char)
        icon_lbl.setStyleSheet("color: {}; font-size: 14px; font-weight: bold;".format(accent))
        layout.addWidget(icon_lbl)

        msg_lbl = QtWidgets.QLabel(str(message))
        msg_lbl.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: 500;")
        layout.addWidget(msg_lbl)

        self.setStyleSheet("""
            QFrame {
                background: rgba(36, 39, 45, 235);
                border: 1px solid #3E4450;
                border-left: 4px solid %s;
                border-radius: 6px;
            }
        """ % accent)

        # Timer to auto-fade or close
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)

    def display(self, duration_ms=3000):
        self.adjustSize()
        parent = self.parentWidget() or maya_main_window()
        if parent:
            geo = parent.geometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + geo.height() - self.height() - 60
            self.move(max(20, x), max(20, y))
        self.show()
        self._timer.start(int(duration_ms))

    def _fade_out(self):
        self.close()


def show_toast(message, level="info", duration_ms=3000, parent=None):
    """
    Show a non-blocking toast notification inside Maya.

    Args:
        message (str): Notification text.
        level (str): 'info', 'success', 'warning', or 'error'.
        duration_ms (int): Display duration in milliseconds.
        parent (QWidget, optional): Parent widget (defaults to Maya Main Window).
    """
    try:
        toast = ToastWidget(message, level=level, parent=parent)
        toast.display(duration_ms=duration_ms)
        return toast
    except Exception:
        return None


__all__ = ["ToastWidget", "show_toast"]
