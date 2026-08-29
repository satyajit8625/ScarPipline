# -*- coding: utf-8 -*-
"""
Advanced Selection Controls for ScarTools Studio Suite.

Provides:
- SegmentedControl: Mutually exclusive connected button group (e.g. [Local | World], [X | Y | Z])
- ToggleSwitch: Modern pill toggle switch ([ON / OFF])
- LabeledSlider: Clean horizontal slider with synchronized numeric display
- SearchableComboBox: Dropdown with inline search filtering
- MultiSelectComboBox: Dropdown with checkboxes for multi-item selection
"""

from __future__ import absolute_import, division, print_function

from .qt import QtCore, QtGui, QtWidgets
from .tokens import (
    COLOR_PRIMARY_BLUE,
    COLOR_PRIMARY_BLUE_HOVER,
    COLOR_BG_INPUT,
    COLOR_BORDER_INPUT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    FORM_LABEL_WIDTH,
    FIELD_HEIGHT,
    INLINE_SPACING,
)


# ===========================================================================
# 1. Segmented Control
# ===========================================================================

class SegmentedControl(QtWidgets.QWidget):
    """
    Connected horizontal pill buttons with mutually exclusive active state.
    Ideal for coordinate spaces (Local/World), symmetry axes (X/Y/Z), etc.
    """

    currentIndexChanged = QtCore.Signal(int)
    currentTextChanged = QtCore.Signal(str)

    def __init__(self, items=None, current=0, accent="primary", parent=None):
        super(SegmentedControl, self).__init__(parent)
        self._items = list(items or [])
        self._current_index = max(0, min(current, len(self._items) - 1)) if self._items else 0
        self._accent = accent
        self._buttons = []

        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._button_group = QtWidgets.QButtonGroup(self)
        self._button_group.setExclusive(True)

        for index, item in enumerate(self._items):
            btn = QtWidgets.QPushButton(str(item))
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setMinimumWidth(50)
            btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            btn.setProperty("segment_index", index)
            btn.setProperty("segment_pos", self._get_pos_class(index, len(self._items)))
            btn.setProperty("accent", self._accent)

            if index == self._current_index:
                btn.setChecked(True)

            btn.clicked.connect(self._on_button_clicked)
            self._button_group.addButton(btn, index)
            self._buttons.append(btn)
            layout.addWidget(btn)

        self._apply_style()

    @staticmethod
    def _get_pos_class(index, total):
        if total <= 1:
            return "single"
        if index == 0:
            return "first"
        if index == total - 1:
            return "last"
        return "middle"

    def _apply_style(self):
        accent_colors = {
            "primary": ("#4F78B8", "#5C87C8"),
            "pipeline": ("#4E937B", "#5BA68C"),
            "rig": ("#766A8E", "#887AA7"),
            "modeling": ("#5F7FA8", "#6D91BD"),
            "texturing": ("#A67C45", "#BA8D52"),
        }
        bg_active, bg_active_hover = accent_colors.get(self._accent, accent_colors["primary"])

        self.setStyleSheet("""
            QPushButton[segment_pos="first"] {
                background: #202227;
                border: 1px solid #363C46;
                border-right: 0;
                border-top-left-radius: 5px;
                border-bottom-left-radius: 5px;
                color: #C0C7D5;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton[segment_pos="middle"] {
                background: #202227;
                border: 1px solid #363C46;
                border-right: 0;
                border-radius: 0;
                color: #C0C7D5;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton[segment_pos="last"] {
                background: #202227;
                border: 1px solid #363C46;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
                color: #C0C7D5;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton[segment_pos="single"] {
                background: #202227;
                border: 1px solid #363C46;
                border-radius: 5px;
                color: #C0C7D5;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover:!checked {
                background: #2B303A;
                color: #FFFFFF;
            }
            QPushButton:checked {
                background: %s;
                border: 1px solid %s;
                color: #FFFFFF;
                font-weight: 700;
            }
            QPushButton:checked:hover {
                background: %s;
            }
        """ % (bg_active, bg_active, bg_active_hover))

    def _on_button_clicked(self):
        sender = self.sender()
        if sender:
            idx = sender.property("segment_index")
            if idx != self._current_index:
                self._current_index = idx
                self.currentIndexChanged.emit(idx)
                self.currentTextChanged.emit(self._items[idx])

    def current_index(self):
        return self._current_index

    def set_current_index(self, index):
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)
            self._current_index = index

    def current_text(self):
        return self._items[self._current_index] if self._items else ""

    def set_current_text(self, text):
        if text in self._items:
            self.set_current_index(self._items.index(text))


def create_segmented_control(items, current=0, accent="primary", parent=None, callback=None):
    ctrl = SegmentedControl(items, current=current, accent=accent, parent=parent)
    if callback:
        ctrl.currentIndexChanged.connect(callback)
    return ctrl


# ===========================================================================
# 2. Toggle Switch
# ===========================================================================

class ToggleSwitch(QtWidgets.QWidget):
    """
    Modern pill toggle switch with smooth indicator and state readout.
    Example: Normalize Weights [ON] / [OFF]
    """

    toggled = QtCore.Signal(bool)

    def __init__(self, text="", checked=False, accent="primary", parent=None):
        super(ToggleSwitch, self).__init__(parent)
        self._text = text
        self._checked = bool(checked)
        self._accent = accent
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFixedHeight(24)
        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)

    def is_checked(self):
        return self._checked

    def set_checked(self, checked):
        if self._checked != bool(checked):
            self._checked = bool(checked)
            self.update()
            self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.set_checked(not self._checked)
            event.accept()
        else:
            super(ToggleSwitch, self).mousePressEvent(event)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)

        # 1. Pill Track (Width: 36px, Height: 18px)
        track_w = 36
        track_h = 18
        track_y = (self.height() - track_h) // 2
        track_rect = QtCore.QRectF(0, track_y, track_w, track_h)

        accent_colors = {
            "primary": QtGui.QColor("#4F78B8"),
            "pipeline": QtGui.QColor("#4E937B"),
            "rig": QtGui.QColor("#766A8E"),
            "modeling": QtGui.QColor("#5F7FA8"),
            "texturing": QtGui.QColor("#A67C45"),
        }
        track_active_color = accent_colors.get(self._accent, accent_colors["primary"])
        track_inactive_color = QtGui.QColor("#2E323A")

        track_color = track_active_color if self._checked else track_inactive_color
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QBrush(track_color))
        p.drawRoundedRect(track_rect, track_h / 2.0, track_h / 2.0)

        # 2. Thumb Knob (Diameter: 14px)
        knob_d = 14
        knob_y = track_y + (track_h - knob_d) / 2.0
        knob_x = (track_w - knob_d - 2) if self._checked else 2

        p.setBrush(QtGui.QBrush(QtGui.QColor("#FFFFFF")))
        p.drawEllipse(QtCore.QRectF(knob_x, knob_y, knob_d, knob_d))

        # 3. Text Label
        if self._text:
            text_x = track_w + 10
            state_str = " [ON]" if self._checked else " [OFF]"
            
            p.setFont(QtGui.QFont("Segoe UI", 9, QtGui.QFont.DemiBold if hasattr(QtGui.QFont, "DemiBold") else 63))
            p.setPen(QtGui.QColor("#E2E8F0"))
            p.drawText(text_x, 0, self.width() - text_x, self.height(), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, self._text)

            # Draw state suffix
            metrics = QtGui.QFontMetrics(p.font())
            lbl_w = metrics.width(self._text)
            state_color = track_active_color if self._checked else QtGui.QColor("#8A94A6")
            p.setPen(state_color)
            p.drawText(text_x + lbl_w, 0, 60, self.height(), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, state_str)

        p.end()

    def sizeHint(self):
        metrics = QtGui.QFontMetrics(QtGui.QFont("Segoe UI", 9))
        w = 36 + (metrics.width(self._text + " [OFF]") + 20 if self._text else 0)
        return QtCore.QSize(w, 24)


def create_toggle_switch(text="", checked=False, accent="primary", parent=None, callback=None):
    sw = ToggleSwitch(text=text, checked=checked, accent=accent, parent=parent)
    if callback:
        sw.toggled.connect(callback)
    return sw


# ===========================================================================
# 3. Labeled Slider with Readout
# ===========================================================================

class LabeledSlider(QtWidgets.QWidget):
    """
    Horizontal slider with label, track, and live formatted numeric display.
    Double-clicking the value resets it to the default value.
    """

    valueChanged = QtCore.Signal(float)

    def __init__(
        self,
        label="Tolerance",
        minimum=0.0,
        maximum=1.0,
        value=0.05,
        step=0.01,
        decimals=2,
        label_width=FORM_LABEL_WIDTH,
        parent=None,
    ):
        super(LabeledSlider, self).__init__(parent)
        self._label_text = label
        self._min = float(minimum)
        self._max = float(maximum)
        self._step = float(step)
        self._decimals = int(decimals)
        self._default = float(value)
        self._label_width = label_width

        # Integer scaling factor for QSlider
        self._scale = int(1.0 / self._step) if self._step > 0 else 100

        self._build_ui()
        self.set_value(value)

    def _build_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(INLINE_SPACING)

        # 1. Name Label
        self.title_lbl = QtWidgets.QLabel(self._label_text)
        self.title_lbl.setObjectName("SliderTitle")
        self.title_lbl.setFixedWidth(self._label_width)
        layout.addWidget(self.title_lbl)

        # 2. QSlider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimum(int(self._min * self._scale))
        self.slider.setMaximum(int(self._max * self._scale))
        self.slider.setFixedHeight(FIELD_HEIGHT)
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider, 1)

        # 3. Value Readout Label
        self.val_lbl = QtWidgets.QLabel()
        self.val_lbl.setObjectName("SliderValue")
        self.val_lbl.setFixedWidth(50)
        self.val_lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.val_lbl.setToolTip("Double-click to reset to default ({:.{}f})".format(self._default, self._decimals))
        self.val_lbl.mouseDoubleClickEvent = self._reset_default
        layout.addWidget(self.val_lbl)

    def _on_slider_changed(self, int_val):
        float_val = round(float(int_val) / float(self._scale), self._decimals)
        self._update_readout(float_val)
        self.valueChanged.emit(float_val)

    def _update_readout(self, val):
        fmt = "{:." + str(self._decimals) + "f}"
        self.val_lbl.setText(fmt.format(val))

    def _reset_default(self, event):
        self.set_value(self._default)

    def value(self):
        return round(float(self.slider.value()) / float(self._scale), self._decimals)

    def set_value(self, val):
        clamped = max(self._min, min(float(val), self._max))
        int_val = int(clamped * self._scale)
        self.slider.setValue(int_val)
        self._update_readout(clamped)


def create_labeled_slider(
    label="Tolerance",
    minimum=0.0,
    maximum=1.0,
    value=0.05,
    step=0.01,
    decimals=2,
    parent=None,
    callback=None,
):
    sl = LabeledSlider(
        label=label,
        minimum=minimum,
        maximum=maximum,
        value=value,
        step=step,
        decimals=decimals,
        parent=parent,
    )
    if callback:
        sl.valueChanged.connect(callback)
    return sl


# ===========================================================================
# 4. Searchable Combo Box
# ===========================================================================

class SearchableComboBox(QtWidgets.QComboBox):
    """
    QComboBox with live filtering search capability.
    Ideal for large item lists like joints, blendshapes, or shaders.
    """

    def __init__(self, parent=None):
        super(SearchableComboBox, self).__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QtWidgets.QComboBox.NoInsert)

        self._filter_model = QtCore.QSortFilterProxyModel(self)
        self._filter_model.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self._filter_model.setSourceModel(self.model())

        # Set up completer
        self.completer = QtWidgets.QCompleter(self._filter_model, self)
        self.completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.setCompleter(self.completer)

        if self.lineEdit():
            self.lineEdit().textEdited.connect(self._filter_model.setFilterFixedString)


# ===========================================================================
# 5. Multi-Selection Combo Box
# ===========================================================================

class MultiSelectComboBox(QtWidgets.QComboBox):
    """
    Dropdown with checkboxes allowing multiple item selections.
    Displays dynamic summary label (e.g. '3 Items Selected').
    """

    selectionChanged = QtCore.Signal(list)

    def __init__(self, placeholder="Select Items...", parent=None):
        super(MultiSelectComboBox, self).__init__(parent)
        self._placeholder = placeholder
        self.view().pressed.connect(self._handle_item_pressed)
        self._model = QtGui.QStandardItemModel(self)
        self.setModel(self._model)
        self._model.itemChanged.connect(self._on_item_changed)

    def _handle_item_pressed(self, index):
        item = self._model.itemFromIndex(index)
        if item:
            item.setCheckState(
                QtCore.Qt.Unchecked if item.checkState() == QtCore.Qt.Checked else QtCore.Qt.Checked
            )

    def _on_item_changed(self, item):
        self._update_display_text()
        self.selectionChanged.emit(self.checked_items())

    def add_items(self, items):
        for item_text in items:
            item = QtGui.QStandardItem(str(item_text))
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
            item.setData(QtCore.Qt.Unchecked, QtCore.Qt.CheckStateRole)
            self._model.appendRow(item)
        self._update_display_text()

    def checked_items(self):
        checked = []
        for i in range(self._model.rowCount()):
            item = self._model.item(i)
            if item and item.checkState() == QtCore.Qt.Checked:
                checked.append(item.text())
        return checked

    def set_checked_items(self, items):
        target = set(items or [])
        self._model.blockSignals(True)
        for i in range(self._model.rowCount()):
            item = self._model.item(i)
            if item:
                item.setCheckState(
                    QtCore.Qt.Checked if item.text() in target else QtCore.Qt.Unchecked
                )
        self._model.blockSignals(False)
        self._update_display_text()

    def _update_display_text(self):
        checked = self.checked_items()
        count = len(checked)
        if count == 0:
            self.setEditText(self._placeholder)
        elif count == 1:
            self.setEditText(checked[0])
        else:
            self.setEditText("{} Selected".format(count))

    def paintEvent(self, event):
        # Prevent default text drawing override
        super(MultiSelectComboBox, self).paintEvent(event)


def create_path_picker(mode="save_file", filter_pattern="All Files (*.*)", placeholder="", parent=None):
    from .widgets import create_path_picker as _cpp
    return _cpp(mode=mode, filter_pattern=filter_pattern, placeholder=placeholder, parent=parent)


def __getattr__(name):
    if name == "PathPickerWidget":
        from .widgets import PathPickerWidget
        return PathPickerWidget
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))


__all__ = [
    "SegmentedControl",
    "create_segmented_control",
    "ToggleSwitch",
    "create_toggle_switch",
    "LabeledSlider",
    "create_labeled_slider",
    "SearchableComboBox",
    "MultiSelectComboBox",
    "PathPickerWidget",
    "create_path_picker",
]
