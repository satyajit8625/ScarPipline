"""Shared Maya Qt compatibility and ScarFall window identity helpers."""

from __future__ import print_function

import os

try:
    import maya.OpenMayaUI as omui
except Exception:
    omui = None

from ..framework.paths import package_root as _package_root

try:
    # Maya 2023 ships with Qt 5. Prefer its native binding even if a user has
    # installed an unrelated PySide6 wheel into Maya's Python environment.
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance
    QT_BINDING = "PySide2"
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance
    QT_BINDING = "PySide6"


def maya_main_window():
    if omui is None:
        return None
    pointer = omui.MQtUtil.mainWindow()
    if pointer is None:
        return None
    return wrapInstance(int(pointer), QtWidgets.QWidget)


def package_root():
    return _package_root()


def app_icon_path():
    path = os.path.join(package_root(), "icons", "scarfall_app_icon.png")
    return path if os.path.isfile(path) else None


def apply_window_icon(widget):
    path = app_icon_path()
    if path:
        widget.setWindowIcon(QtGui.QIcon(path))
    return path


__all__ = [
    "QT_BINDING",
    "QtCore",
    "QtGui",
    "QtWidgets",
    "wrapInstance",
    "maya_main_window",
    "package_root",
    "app_icon_path",
    "apply_window_icon",
]
