# -*- coding: utf-8 -*-
"""Advanced Specialized DCC Interactive Widgets for ScarTools."""

from __future__ import absolute_import, division, print_function

import json
import math
import os
import subprocess
import sys

from .qt import QtCore, QtGui, QtWidgets, maya_main_window
from .tokens import (
    COLOR_BG_PANEL,
    COLOR_BG_INPUT,
    COLOR_BORDER_DEFAULT,
    COLOR_PRIMARY_BLUE,
    COLOR_STATUS_SUCCESS,
    COLOR_STATUS_WARNING,
    COLOR_STATUS_ERROR,
    FONT_FAMILY_BASE,
    FONT_FAMILY_MONO,
    FIELD_HEIGHT,
    INLINE_SPACING,
)


# ===========================================================================
# 1. Vector3 Input (X, Y, Z Coordinate Row)
# ===========================================================================

class Vector3Input(QtWidgets.QWidget):
    """3-Axis linked coordinate input [X, Y, Z] with color badges and scrubbing."""

    valueChanged = QtCore.Signal(float, float, float)

    def __init__(self, x=0.0, y=0.0, z=0.0, minimum=-99999.0, maximum=99999.0, decimals=3, step=0.1, parent=None):
        super(Vector3Input, self).__init__(parent)
        self._decimals = decimals
        self._step = step

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # X SpinBox
        self.lbl_x = QtWidgets.QLabel("X")
        self.lbl_x.setObjectName("AxisBadgeX")
        self.lbl_x.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_x.setFixedWidth(20)
        self.spin_x = QtWidgets.QDoubleSpinBox()
        self.spin_x.setRange(minimum, maximum)
        self.spin_x.setDecimals(decimals)
        self.spin_x.setSingleStep(step)
        self.spin_x.setValue(x)
        self.spin_x.setFixedHeight(FIELD_HEIGHT - 4)

        # Y SpinBox
        self.lbl_y = QtWidgets.QLabel("Y")
        self.lbl_y.setObjectName("AxisBadgeY")
        self.lbl_y.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_y.setFixedWidth(20)
        self.spin_y = QtWidgets.QDoubleSpinBox()
        self.spin_y.setRange(minimum, maximum)
        self.spin_y.setDecimals(decimals)
        self.spin_y.setSingleStep(step)
        self.spin_y.setValue(y)
        self.spin_y.setFixedHeight(FIELD_HEIGHT - 4)

        # Z SpinBox
        self.lbl_z = QtWidgets.QLabel("Z")
        self.lbl_z.setObjectName("AxisBadgeZ")
        self.lbl_z.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_z.setFixedWidth(20)
        self.spin_z = QtWidgets.QDoubleSpinBox()
        self.spin_z.setRange(minimum, maximum)
        self.spin_z.setDecimals(decimals)
        self.spin_z.setSingleStep(step)
        self.spin_z.setValue(z)
        self.spin_z.setFixedHeight(FIELD_HEIGHT - 4)

        layout.addWidget(self.lbl_x)
        layout.addWidget(self.spin_x, 1)
        layout.addWidget(self.lbl_y)
        layout.addWidget(self.spin_y, 1)
        layout.addWidget(self.lbl_z)
        layout.addWidget(self.spin_z, 1)

        self.spin_x.valueChanged.connect(self._on_change)
        self.spin_y.valueChanged.connect(self._on_change)
        self.spin_z.valueChanged.connect(self._on_change)

    def _on_change(self):
        self.valueChanged.emit(self.spin_x.value(), self.spin_y.value(), self.spin_z.value())

    def value(self):
        return (self.spin_x.value(), self.spin_y.value(), self.spin_z.value())

    def set_value(self, x, y, z):
        self.spin_x.blockSignals(True)
        self.spin_y.blockSignals(True)
        self.spin_z.blockSignals(True)
        self.spin_x.setValue(float(x))
        self.spin_y.setValue(float(y))
        self.spin_z.setValue(float(z))
        self.spin_x.blockSignals(False)
        self.spin_y.blockSignals(False)
        self.spin_z.blockSignals(False)
        self._on_change()

    def reset_to_zero(self):
        self.set_value(0.0, 0.0, 0.0)


def create_vector3_input(x=0.0, y=0.0, z=0.0, parent=None):
    return Vector3Input(x, y, z, parent=parent)


# ===========================================================================
# 2. Path Picker Widget (Files / Folders with Drag & Drop)
# ===========================================================================

class PathPickerWidget(QtWidgets.QWidget):
    """Path input with browse button, drag & drop support, and Open in Explorer."""

    pathChanged = QtCore.Signal(str)

    def __init__(self, mode="file", filter_pattern="All Files (*.*)", placeholder="Select file...", parent=None):
        super(PathPickerWidget, self).__init__(parent)
        self._mode = mode  # 'file', 'save_file', or 'directory'
        self._filter = filter_pattern
        self.setAcceptDrops(True)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.path_input = QtWidgets.QLineEdit()
        self.path_input.setPlaceholderText(placeholder)
        self.path_input.setFixedHeight(FIELD_HEIGHT - 2)
        self.path_input.setClearButtonEnabled(True)

        self.browse_btn = QtWidgets.QToolButton()
        self.browse_btn.setText("📁")
        self.browse_btn.setToolTip("Browse path...")
        self.browse_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.browse_btn.setFixedSize(28, FIELD_HEIGHT - 2)

        self.open_dir_btn = QtWidgets.QToolButton()
        self.open_dir_btn.setText("↗")
        self.open_dir_btn.setToolTip("Open containing folder in Explorer")
        self.open_dir_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.open_dir_btn.setFixedSize(24, FIELD_HEIGHT - 2)

        layout.addWidget(self.path_input, 1)
        layout.addWidget(self.browse_btn)
        layout.addWidget(self.open_dir_btn)

        self.browse_btn.clicked.connect(self._browse)
        self.open_dir_btn.clicked.connect(self._open_explorer)
        self.path_input.textChanged.connect(self.pathChanged.emit)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            local_path = urls[0].toLocalFile()
            if local_path:
                self.set_path(local_path)
                event.acceptProposedAction()

    def _browse(self):
        cur = self.path() or os.path.expanduser("~")
        if self._mode == "directory":
            chosen = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory", cur)
        elif self._mode == "save_file":
            chosen, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save File", cur, self._filter)
        else:
            chosen, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select File", cur, self._filter)

        if chosen:
            self.set_path(chosen)

    def _open_explorer(self):
        p = self.path()
        if not p:
            return
        folder = p if os.path.isdir(p) else os.path.dirname(p)
        if os.path.exists(folder):
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform.startswith("darwin"):
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])

    def path(self):
        return self.path_input.text().strip()

    def set_path(self, path_str):
        self.path_input.setText(str(path_str or ""))


def create_path_picker(mode="file", filter_pattern="All Files (*.*)", placeholder="Select path...", parent=None):
    return PathPickerWidget(mode=mode, filter_pattern=filter_pattern, placeholder=placeholder, parent=parent)


# ===========================================================================
# 3. Interactive UV Tile Matrix Grid (UDIMs 1001-1090)
# ===========================================================================

class UVTileGrid(QtWidgets.QWidget):
    """Interactive 10x10 UV Tile Matrix representing UDIM blocks (1001-1090)."""

    selectionChanged = QtCore.Signal(list)
    tileClicked = QtCore.Signal(int)

    def __init__(self, u_count=10, v_count=5, start_udim=1001, parent=None):
        super(UVTileGrid, self).__init__(parent)
        self._u_count = max(1, min(10, int(u_count)))
        self._v_count = max(1, min(10, int(v_count)))
        self._start_udim = int(start_udim)
        self._tile_states = {}  # udim: 'empty' | 'active' | 'missing' | 'warning'
        self._selected_udims = set()
        self.setMinimumSize(240, 130)
        self.setMouseTracking(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def set_tile_state(self, udim, state="active"):
        self._tile_states[int(udim)] = state
        self.update()

    def set_tile_states(self, states_dict):
        self._tile_states = {int(k): str(v) for k, v in states_dict.items()}
        self.update()

    def selected_udims(self):
        return sorted(list(self._selected_udims))

    def set_selected_udims(self, udims):
        self._selected_udims = set(int(u) for u in udims)
        self.update()
        self.selectionChanged.emit(self.selected_udims())

    def clear_selection(self):
        self._selected_udims.clear()
        self.update()
        self.selectionChanged.emit([])

    def _udim_at_pos(self, pos):
        w = float(self.width()) / self._u_count
        h = float(self.height()) / self._v_count
        col = int(pos.x() / w)
        row = int(pos.y() / h)
        # Flip row so row 0 is at bottom (standard UV space: V starts at bottom)
        v_idx = (self._v_count - 1) - row
        if 0 <= col < self._u_count and 0 <= v_idx < self._v_count:
            return self._start_udim + (v_idx * 10) + col
        return None

    def mousePressEvent(self, event):
        udim = self._udim_at_pos(event.pos())
        if udim:
            if event.modifiers() & QtCore.Qt.ShiftModifier or event.modifiers() & QtCore.Qt.ControlModifier:
                if udim in self._selected_udims:
                    self._selected_udims.remove(udim)
                else:
                    self._selected_udims.add(udim)
            else:
                self._selected_udims = {udim}
            self.update()
            self.tileClicked.emit(udim)
            self.selectionChanged.emit(self.selected_udims())

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)

        w = float(self.width()) / self._u_count
        h = float(self.height()) / self._v_count

        state_colors = {
            "empty": QtGui.QColor("#181A1F"),
            "active": QtGui.QColor("#4E937B"),
            "missing": QtGui.QColor("#E06C6C"),
            "warning": QtGui.QColor("#D6B36A"),
        }

        for col in range(self._u_count):
            for v_idx in range(self._v_count):
                row = (self._v_count - 1) - v_idx
                udim = self._start_udim + (v_idx * 10) + col
                rect = QtCore.QRectF(col * w + 1, row * h + 1, w - 2, h - 2)

                is_sel = udim in self._selected_udims
                state = self._tile_states.get(udim, "empty")
                base_color = state_colors.get(state, state_colors["empty"])

                if is_sel:
                    p.setBrush(QtGui.QColor("#4F78B8"))
                    p.setPen(QtGui.QPen(QtGui.QColor("#8AB4F8"), 2.0))
                else:
                    p.setBrush(base_color)
                    p.setPen(QtGui.QPen(QtGui.QColor("#2F3540"), 1.0))

                p.drawRoundedRect(rect, 3, 3)

                # Draw UDIM text label
                p.setPen(QtGui.QColor("#FFFFFF" if is_sel or state != "empty" else "#656C78"))
                font = p.font()
                font.setPointSize(8)
                font.setBold(True)
                p.setFont(font)
                p.drawText(rect, QtCore.Qt.AlignCenter, str(udim))

        p.end()


def create_uv_tile_grid(u_count=10, v_count=4, parent=None):
    return UVTileGrid(u_count=u_count, v_count=v_count, parent=parent)


# ===========================================================================
# 4. Falloff Curve / Spline Remap Graph Widget
# ===========================================================================

class CurveEditorWidget(QtWidgets.QWidget):
    """Interactive 2D Bézier curve graph for falloff curves and weight remapping."""

    curveChanged = QtCore.Signal()

    def __init__(self, parent=None):
        super(CurveEditorWidget, self).__init__(parent)
        # Normalized points [(x0, y0), (x1, y1), ...]
        self._points = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
        self._selected_idx = -1
        self.setMinimumSize(220, 140)
        self.setMouseTracking(True)
        self.setCursor(QtCore.Qt.CrossCursor)

    def points(self):
        return list(self._points)

    def set_points(self, pts):
        self._points = sorted(list(pts), key=lambda p: p[0])
        self.update()
        self.curveChanged.emit()

    def set_preset(self, name):
        if name == "linear":
            self.set_points([(0.0, 0.0), (1.0, 1.0)])
        elif name == "ease_in":
            self.set_points([(0.0, 0.0), (0.7, 0.2), (1.0, 1.0)])
        elif name == "ease_out":
            self.set_points([(0.0, 0.0), (0.3, 0.8), (1.0, 1.0)])
        elif name == "smooth":
            self.set_points([(0.0, 0.0), (0.25, 0.05), (0.75, 0.95), (1.0, 1.0)])
        elif name == "bell":
            self.set_points([(0.0, 0.0), (0.5, 1.0), (1.0, 0.0)])

    def evaluate(self, t):
        """Evaluate curve value at normalized time t (0.0 to 1.0) with linear interpolation."""
        t = max(0.0, min(1.0, float(t)))
        if not self._points:
            return t
        if t <= self._points[0][0]:
            return self._points[0][1]
        if t >= self._points[-1][0]:
            return self._points[-1][1]

        for i in range(len(self._points) - 1):
            p0 = self._points[i]
            p1 = self._points[i + 1]
            if p0[0] <= t <= p1[0]:
                span = p1[0] - p0[0]
                if span <= 1e-6:
                    return p0[1]
                ratio = (t - p0[0]) / span
                # Smooth cubic hermite interpolation
                smooth_ratio = ratio * ratio * (3.0 - 2.0 * ratio)
                return p0[1] + (p1[1] - p0[1]) * smooth_ratio
        return t

    def _to_screen(self, nx, ny):
        m = 12.0
        w = float(self.width()) - (2.0 * m)
        h = float(self.height()) - (2.0 * m)
        sx = m + (nx * w)
        sy = m + ((1.0 - ny) * h)
        return QtCore.QPointF(sx, sy)

    def _to_norm(self, sx, sy):
        m = 12.0
        w = float(self.width()) - (2.0 * m)
        h = float(self.height()) - (2.0 * m)
        nx = max(0.0, min(1.0, (sx - m) / max(1.0, w)))
        ny = max(0.0, min(1.0, 1.0 - ((sy - m) / max(1.0, h))))
        return (nx, ny)

    def mousePressEvent(self, event):
        pos = event.pos()
        self._selected_idx = -1
        for i, pt in enumerate(self._points):
            s_pt = self._to_screen(pt[0], pt[1])
            if (pos - s_pt).manhattanLength() < 10:
                self._selected_idx = i
                break

        if self._selected_idx == -1 and event.button() == QtCore.Qt.LeftButton:
            # Add point
            nx, ny = self._to_norm(pos.x(), pos.y())
            self._points.append((nx, ny))
            self._points = sorted(self._points, key=lambda p: p[0])
            self._selected_idx = self._points.index((nx, ny))
            self.update()
            self.curveChanged.emit()

    def mouseMoveEvent(self, event):
        if self._selected_idx >= 0 and event.buttons() & QtCore.Qt.LeftButton:
            nx, ny = self._to_norm(event.pos().x(), event.pos().y())
            # Lock end points X to 0 and 1
            if self._selected_idx == 0:
                nx = 0.0
            elif self._selected_idx == len(self._points) - 1:
                nx = 1.0
            self._points[self._selected_idx] = (nx, ny)
            self._points = sorted(self._points, key=lambda p: p[0])
            self.update()
            self.curveChanged.emit()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)

        # Background grid
        p.fillRect(self.rect(), QtGui.QColor("#14161A"))
        p.setPen(QtGui.QPen(QtGui.QColor("#242832"), 1.0))
        for g in (0.25, 0.5, 0.75):
            pt1 = self._to_screen(g, 0.0)
            pt2 = self._to_screen(g, 1.0)
            p.drawLine(pt1, pt2)
            pt3 = self._to_screen(0.0, g)
            pt4 = self._to_screen(1.0, g)
            p.drawLine(pt3, pt4)

        # Draw curve path
        if len(self._points) >= 2:
            path = QtGui.QPainterPath()
            first = self._to_screen(0.0, self.evaluate(0.0))
            path.moveTo(first)
            samples = 40
            for s in range(1, samples + 1):
                t = float(s) / samples
                val = self.evaluate(t)
                path.lineTo(self._to_screen(t, val))

            p.setPen(QtGui.QPen(QtGui.QColor("#4F78B8"), 2.25))
            p.drawPath(path)

        # Draw control points
        for i, pt in enumerate(self._points):
            s_pt = self._to_screen(pt[0], pt[1])
            is_sel = (i == self._selected_idx)
            p.setBrush(QtGui.QColor("#8AB4F8" if is_sel else "#FFFFFF"))
            p.setPen(QtGui.QPen(QtGui.QColor("#1E222A"), 1.5))
            p.drawEllipse(s_pt, 4.5, 4.5)

        p.end()


def create_curve_editor(parent=None):
    return CurveEditorWidget(parent=parent)


# ===========================================================================
# 5. Studio Palette Grid Swatch Picker
# ===========================================================================

class PaletteGrid(QtWidgets.QWidget):
    """Studio palette bar with 16 studio preset swatches for 1-click coloring."""

    colorSelected = QtCore.Signal(QtGui.QColor)

    PALETTE = [
        "#E06C75", "#E5C07B", "#98C379", "#56B6C2",
        "#61AFEF", "#C678DD", "#ABB2BF", "#FFFFFF",
        "#D19A66", "#766A8E", "#4E937B", "#5F7FA8",
        "#E76F51", "#2A9D8F", "#E9C46A", "#264653",
    ]

    def __init__(self, parent=None):
        super(PaletteGrid, self).__init__(parent)
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        for i, hex_col in enumerate(self.PALETTE):
            row = i // 8
            col = i % 8
            btn = QtWidgets.QToolButton()
            btn.setFixedSize(22, 22)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QToolButton { background-color: %s; border: 1px solid #363C46; border-radius: 3px; }"
                "QToolButton:hover { border: 2px solid #FFFFFF; }" % hex_col
            )
            color_obj = QtGui.QColor(hex_col)
            btn.clicked.connect(lambda c=color_obj: self.colorSelected.emit(c))
            layout.addWidget(btn, row, col)


def create_palette_grid(parent=None):
    return PaletteGrid(parent=parent)


# ===========================================================================
# 6. Token Tag Input Chips
# ===========================================================================

class TokenTagInput(QtWidgets.QWidget):
    """Dynamic chip tag input container with auto-complete and tag removal."""

    tagsChanged = QtCore.Signal(list)

    def __init__(self, placeholder="Add tag + Enter...", suggestions=None, parent=None):
        super(TokenTagInput, self).__init__(parent)
        self._tags = []
        self._suggestions = suggestions or ["#hero", "#lod0", "#prop", "#rig", "#facial", "#blendshape"]

        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)

        self.input_field = QtWidgets.QLineEdit()
        self.input_field.setPlaceholderText(placeholder)
        self.input_field.setFixedHeight(24)
        self.input_field.setStyleSheet("background: transparent; border: none; color: #FFFFFF; font-size: 11px;")
        self._layout.addWidget(self.input_field)

        self.setStyleSheet("TokenTagInput { background: #181818; border: 1px solid #484848; border-radius: 4px; }")

        # Completer
        completer = QtWidgets.QCompleter(self._suggestions, self)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.input_field.setCompleter(completer)
        self.input_field.returnPressed.connect(self._add_from_input)

    def _add_from_input(self):
        text = self.input_field.text().strip()
        if text and text not in self._tags:
            self.add_tag(text)
            self.input_field.clear()

    def add_tag(self, tag_name):
        tag_name = str(tag_name).strip()
        if tag_name and tag_name not in self._tags:
            self._tags.append(tag_name)
            chip = QtWidgets.QFrame()
            chip.setObjectName("TagChip")
            chip_layout = QtWidgets.QHBoxLayout(chip)
            chip_layout.setContentsMargins(4, 1, 4, 1)
            chip_layout.setSpacing(4)

            lbl = QtWidgets.QLabel(tag_name)
            lbl.setObjectName("TagLabel")
            x_btn = QtWidgets.QToolButton()
            x_btn.setObjectName("TagRemoveBtn")
            x_btn.setText("×")
            x_btn.setFixedSize(14, 14)
            x_btn.setCursor(QtCore.Qt.PointingHandCursor)
            x_btn.clicked.connect(lambda: self.remove_tag(tag_name, chip))

            chip_layout.addWidget(lbl)
            chip_layout.addWidget(x_btn)

            # Insert before input field
            self._layout.insertWidget(self._layout.count() - 1, chip)
            self.tagsChanged.emit(self.tags())

    def remove_tag(self, tag_name, chip_widget):
        if tag_name in self._tags:
            self._tags.remove(tag_name)
            self._layout.removeWidget(chip_widget)
            chip_widget.deleteLater()
            self.tagsChanged.emit(self.tags())

    def tags(self):
        return list(self._tags)

    def set_tags(self, tags_list):
        for t in list(self._tags):
            self.remove_tag(t, None)
        for t in tags_list:
            self.add_tag(t)


def create_token_input(placeholder="Add tag + Enter...", parent=None):
    return TokenTagInput(placeholder=placeholder, parent=parent)


__all__ = [
    "Vector3Input",
    "create_vector3_input",
    "PathPickerWidget",
    "create_path_picker",
    "UVTileGrid",
    "create_uv_tile_grid",
    "CurveEditorWidget",
    "create_curve_editor",
    "PaletteGrid",
    "create_palette_grid",
    "TokenTagInput",
    "create_token_input",
]
