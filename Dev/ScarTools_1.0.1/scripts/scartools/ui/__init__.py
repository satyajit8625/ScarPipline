"""Reusable ScarTools Qt components shared by department-tool windows."""

from __future__ import print_function

import sys
import re
import weakref

from .qt import QtCore, QtGui, QtWidgets, app_icon_path, apply_window_icon, maya_main_window
from ..framework.paths import resolve_icon
from ..framework.lifecycle import register_window
from .theme import apply as apply_theme
from .tokens import *


_ROLLUP_WINDOWS = weakref.WeakValueDictionary()
_NATIVE_ROLLUP_FILTER = None
_WM_NCLBUTTONDBLCLK = 0x00A3
_HTCAPTION = 2


def _windows_message(message):
    """Return a Windows MSG for a Qt native-event pointer."""
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes
        from ctypes import wintypes
        return ctypes.cast(
            int(message), ctypes.POINTER(wintypes.MSG)
        ).contents
    except Exception:
        return None


def _non_client_double_click_type():
    """Return Qt's native-title-bar double-click event enum."""
    event_type = getattr(QtCore.QEvent, "NonClientAreaMouseButtonDblClick", None)
    if event_type is None and hasattr(QtCore.QEvent, "Type"):
        event_type = getattr(
            QtCore.QEvent.Type, "NonClientAreaMouseButtonDblClick", None
        )
    return event_type


def _queue_rollup(window):
    """Queue exactly one roll-up toggle for the current native event."""
    if getattr(window, "_scartools_rollup_pending", False):
        return
    window._scartools_rollup_pending = True

    def apply_toggle():
        try:
            toggle_rollup(window)
        finally:
            window._scartools_rollup_pending = False

    QtCore.QTimer.singleShot(0, apply_toggle)


class _TitleBarRollupEventFilter(QtCore.QObject):
    """Qt-level title-bar double-click handler used alongside the native hook."""

    def eventFilter(self, watched, event):
        event_type = _non_client_double_click_type()
        if event_type is not None and event.type() == event_type:
            _queue_rollup(watched)
            event.accept()
            return True
        return super(_TitleBarRollupEventFilter, self).eventFilter(watched, event)


class _NativeTitleBarRollupFilter(QtCore.QAbstractNativeEventFilter):
    """Convert a Windows title-bar double-click into ScarTools roll-up."""

    def nativeEventFilter(self, event_type, message):
        del event_type
        try:
            native_message = _windows_message(message)
            if native_message is None:
                return False, 0
            msg_code = getattr(native_message, "message", None)
            w_param = getattr(native_message, "wParam", None)
            if msg_code is None or w_param is None:
                return False, 0
            if int(msg_code) == _WM_NCLBUTTONDBLCLK and int(w_param) == _HTCAPTION:
                hwnd_val = getattr(native_message, "hwnd", getattr(native_message, "hWnd", None))
                if hwnd_val is None:
                    return False, 0
                window_handle = int(hwnd_val)
                window = _ROLLUP_WINDOWS.get(window_handle)
                if window is None:
                    candidate = QtWidgets.QWidget.find(window_handle)
                    if candidate is not None:
                        candidate = candidate.window()
                        if getattr(candidate, "_scartools_rollup_enabled", False):
                            window = candidate
                            _ROLLUP_WINDOWS[window_handle] = window
                if window is not None:
                    _queue_rollup(window)
                    return True, 0
        except Exception:
            return False, 0
        return False, 0



def _install_native_rollup_filter():
    global _NATIVE_ROLLUP_FILTER
    if _NATIVE_ROLLUP_FILTER is not None:
        return _NATIVE_ROLLUP_FILTER
    application = QtCore.QCoreApplication.instance()
    if application is None:
        return None
    _NATIVE_ROLLUP_FILTER = _NativeTitleBarRollupFilter()
    application.installNativeEventFilter(_NATIVE_ROLLUP_FILTER)
    return _NATIVE_ROLLUP_FILTER


def configure_button(button, primary=False, fixed_width=None, role=None):
    """Apply the suite-wide role, height, and optional width to a button."""
    role = str(role or ("primary" if primary else "secondary"))
    button.setProperty("role", role)
    button.setFixedHeight(
        PRIMARY_BUTTON_HEIGHT if role == "primary" else SECONDARY_BUTTON_HEIGHT
    )
    if fixed_width:
        button.setFixedWidth(int(fixed_width))
    elif role != "primary":
        button.setMinimumWidth(SECONDARY_BUTTON_MIN_WIDTH)
    return button


def create_button(text, role="secondary", fixed_width=None, parent=None):
    """Create a consistently named and sized ScarTools button."""
    button = QtWidgets.QPushButton(str(text), parent)
    object_names = {
        "primary": "PrimaryButton",
        "danger": "DangerButton",
        "log": "ViewLogButton",
    }
    if role in object_names:
        button.setObjectName(object_names[role])
    return configure_button(
        button,
        primary=role == "primary",
        fixed_width=fixed_width,
        role=role,
    )


def configure_window(window, minimum, default=None):
    """Apply a predictable minimum/default size to a suite window."""
    window.setMinimumSize(int(minimum[0]), int(minimum[1]))
    if default is not None:
        window.resize(int(default[0]), int(default[1]))
    return window


def configure_root_layout(layout, embedded=False):
    """Apply the shared outer margin and vertical spacing."""
    if embedded:
        layout.setContentsMargins(0, NAV_CONTENT_GAP, 0, 0)
    else:
        layout.setContentsMargins(
            WINDOW_MARGIN, WINDOW_MARGIN, WINDOW_MARGIN, WINDOW_MARGIN
        )
    layout.setSpacing(WINDOW_SPACING)
    return layout


def configure_group_layout(layout):
    """Apply shared insets to group-box contents."""
    layout.setContentsMargins(
        GROUP_MARGIN_X,
        GROUP_MARGIN_TOP,
        GROUP_MARGIN_X,
        GROUP_MARGIN_BOTTOM,
    )
    if hasattr(layout, "setSpacing"):
        layout.setSpacing(GROUP_SPACING)
    return layout


def configure_field(widget, minimum_width=None):
    """Normalize line-edit and combo-box heights across the suite."""
    widget.setMinimumHeight(FIELD_HEIGHT)
    if minimum_width is not None:
        widget.setMinimumWidth(int(minimum_width))
    return widget


def configure_table(table, minimum_height=TABLE_MIN_HEIGHT):
    """Normalize the minimum working area and interaction of data tables."""
    table.setMinimumHeight(int(minimum_height))
    table.setObjectName("MeshTable")
    table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
    table.setAlternatingRowColors(True)
    table.setShowGrid(True)
    table.setWordWrap(False)
    table.setFocusPolicy(QtCore.Qt.StrongFocus)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(34)
    table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setDefaultAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
    return table


def configure_table_columns(
    table,
    stretch_columns=(),
    contents_columns=(),
    fixed_columns=None,
):
    """Apply explicit, reusable resize rules to a pipeline table."""
    fixed_columns = dict(fixed_columns or {})
    stretch_columns = set(int(index) for index in stretch_columns)
    contents_columns = set(int(index) for index in contents_columns)
    header = table.horizontalHeader()
    for index in range(table.columnCount()):
        if index in fixed_columns:
            header.setSectionResizeMode(index, QtWidgets.QHeaderView.Fixed)
            header.resizeSection(index, int(fixed_columns[index]))
        elif index in stretch_columns:
            header.setSectionResizeMode(index, QtWidgets.QHeaderView.Stretch)
        elif index in contents_columns:
            header.setSectionResizeMode(
                index, QtWidgets.QHeaderView.ResizeToContents
            )
        else:
            header.setSectionResizeMode(index, QtWidgets.QHeaderView.Interactive)
    return table


def create_data_table(
    headers,
    stretch_columns=(),
    contents_columns=(),
    fixed_columns=None,
    minimum_height=TABLE_MIN_HEIGHT,
    extended_selection=False,
    parent=None,
):
    """Create a standard ScarTools results table with declared column rules."""
    labels = [str(label) for label in headers]
    table = QtWidgets.QTableWidget(0, len(labels), parent)
    table.setHorizontalHeaderLabels(labels)
    configure_table(table, minimum_height=minimum_height)
    configure_table_columns(
        table,
        stretch_columns=stretch_columns,
        contents_columns=contents_columns,
        fixed_columns=fixed_columns,
    )
    table.setSelectionMode(
        QtWidgets.QAbstractItemView.ExtendedSelection
        if extended_selection
        else QtWidgets.QAbstractItemView.SingleSelection
    )
    return table


def create_section_panel(title, accent="neutral", layout_kind="vertical", parent=None):
    """Create a bordered section whose title never intersects its border."""
    panel = QtWidgets.QFrame(parent)
    panel.setObjectName("SectionPanel")
    panel.setProperty("accent", str(accent))
    shell = QtWidgets.QVBoxLayout(panel)
    shell.setContentsMargins(
        GROUP_MARGIN_X,
        10,
        GROUP_MARGIN_X,
        GROUP_MARGIN_BOTTOM,
    )
    shell.setSpacing(GROUP_SPACING)

    title_label = QtWidgets.QLabel(str(title))
    title_label.setObjectName("SectionTitle")
    shell.addWidget(title_label)

    kinds = {
        "vertical": QtWidgets.QVBoxLayout,
        "horizontal": QtWidgets.QHBoxLayout,
        "grid": QtWidgets.QGridLayout,
    }
    try:
        layout_class = kinds[str(layout_kind)]
    except KeyError:
        raise ValueError("Unknown section layout kind: {}".format(layout_kind))
    content = layout_class()
    content.setContentsMargins(0, 0, 0, 0)
    content.setSpacing(GROUP_SPACING)
    shell.addLayout(content)
    return panel, content, title_label



def create_compact_section(title, accent="neutral", layout_kind="vertical", parent=None):
    """Create a compact bordered section panel with clean title header."""
    panel = QtWidgets.QFrame(parent)
    panel.setObjectName("SectionPanel")
    panel.setProperty("accent", str(accent))
    shell = QtWidgets.QVBoxLayout(panel)
    shell.setContentsMargins(10, 7, 10, 8)
    shell.setSpacing(6)

    title_label = QtWidgets.QLabel(str(title))
    title_label.setObjectName("SectionTitle")
    shell.addWidget(title_label)

    kinds = {
        "vertical": QtWidgets.QVBoxLayout,
        "horizontal": QtWidgets.QHBoxLayout,
        "grid": QtWidgets.QGridLayout,
    }
    layout_class = kinds.get(str(layout_kind), QtWidgets.QVBoxLayout)
    content = layout_class()
    content.setContentsMargins(0, 0, 0, 0)
    content.setSpacing(6)
    shell.addLayout(content)
    return panel, content, title_label


def create_labeled_input(label_text, placeholder="", parent=None):
    """Create a standard labeled QLineEdit layout."""
    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    lbl = QtWidgets.QLabel(str(label_text), parent)
    edit = QtWidgets.QLineEdit(parent)
    if placeholder:
        edit.setPlaceholderText(str(placeholder))
    configure_field(edit)
    layout.addWidget(lbl)
    layout.addWidget(edit)
    return layout, edit, lbl



def create_navigation_tabs(parent=None):
    """Create full-width navigation for a multi-workflow tool window."""
    tabs = QtWidgets.QTabWidget(parent)
    tabs.setObjectName("MainTabs")
    tabs.setDocumentMode(False)
    tabs.setMovable(False)
    tabs.setTabsClosable(False)
    tabs.tabBar().setExpanding(True)
    tabs.tabBar().setDrawBase(False)
    tabs.tabBar().setUsesScrollButtons(False)
    tabs.tabBar().setElideMode(QtCore.Qt.ElideNone)
    return tabs


def create_operation_group(
    modes=("Export", "Import"),
    help_text="",
    parent=None,
):
    """Create the shared Mode + help operation panel used by pipeline tools."""
    group, layout, _title = create_section_panel(
        "Operation", accent="operation", layout_kind="horizontal", parent=parent
    )

    label = QtWidgets.QLabel("Mode")
    label.setMinimumWidth(FORM_LABEL_WIDTH)
    combo = QtWidgets.QComboBox()
    combo.addItems([str(mode) for mode in modes])
    configure_field(combo, minimum_width=170)
    help_label = QtWidgets.QLabel(str(help_text))
    help_label.setObjectName("Muted")
    help_label.setWordWrap(True)
    help_label.setSizePolicy(
        QtWidgets.QSizePolicy.Expanding,
        QtWidgets.QSizePolicy.Preferred,
    )

    layout.addWidget(label)
    layout.addWidget(combo)
    layout.addSpacing(INLINE_SPACING)
    layout.addWidget(help_label)
    layout.addStretch(1)
    return group, combo, help_label


def create_status_bar(text="Ready", parent=None, include_log=False):
    """Create the standard dot/status footer used by every tool window."""
    bar = QtWidgets.QFrame(parent)
    bar.setObjectName("StatusBar")
    bar.setMinimumHeight(SECONDARY_BUTTON_HEIGHT)
    layout = QtWidgets.QHBoxLayout(bar)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(GROUP_SPACING)

    dot = QtWidgets.QLabel("●")
    dot.setObjectName("StatusDot")
    dot.setProperty("state", "idle")
    dot.setFixedWidth(STATUS_DOT_WIDTH)
    dot.setAlignment(QtCore.Qt.AlignCenter)
    label = QtWidgets.QLabel(str(text))
    label.setObjectName("Status")
    label.setProperty("state", "idle")
    layout.addWidget(dot)
    layout.addWidget(label, 1)

    log_button = QtWidgets.QPushButton(bar)
    log_button.hide()
    if include_log:
        log_button = create_button(
            "View Log", role="log", fixed_width=LOG_BUTTON_WIDTH
        )
        layout.addWidget(log_button)
    return bar, dot, label, log_button, layout


def create_action_footer(
    action_text,
    message="",
    parent=None,
    include_log=False,
):
    """Create the stable message/action/status footer used by workflows."""
    footer = QtWidgets.QFrame(parent)

    footer.setObjectName("ActionFooter")
    footer.setMinimumHeight(ACTION_FOOTER_MIN_HEIGHT)
    layout = QtWidgets.QVBoxLayout(footer)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(GROUP_SPACING)

    action_row = QtWidgets.QHBoxLayout()
    action_row.setSpacing(INLINE_SPACING)
    message_label = QtWidgets.QLabel(str(message))
    message_label.setObjectName("Warning")
    message_label.setProperty("state", "neutral")
    message_label.setWordWrap(True)
    action_button = create_button(
        action_text,
        role="primary",
        fixed_width=PRIMARY_BUTTON_WIDTH,
    )
    action_row.addWidget(message_label, 1)
    action_row.addWidget(action_button, 0, QtCore.Qt.AlignVCenter)
    layout.addLayout(action_row)

    status_bar, dot, status_label, log_button, status_layout = create_status_bar(
        parent=footer,
        include_log=include_log,
    )
    layout.addWidget(status_bar)
    return (
        footer,
        message_label,
        action_button,
        dot,
        status_label,
        log_button,
        status_layout,
    )


def create_brand_header(title, subtitle, parent=None):
    """Create the shared ScarFall-branded tool header.

    The logo identifies the suite while department and tool icons remain in
    Maya's menu, avoiding mixed visual meaning inside the tool window.
    """
    header = QtWidgets.QFrame(parent)
    header.setObjectName("Header")
    layout = QtWidgets.QHBoxLayout(header)
    layout.setContentsMargins(12, 9, 14, 9)
    layout.setSpacing(11)

    logo = QtWidgets.QLabel()
    logo.setObjectName("BrandHeaderLogo")
    logo.setFixedSize(42, 42)
    logo.setAlignment(QtCore.Qt.AlignCenter)
    path = app_icon_path()
    if path:
        pixmap = QtGui.QPixmap(path)
        logo.setPixmap(
            pixmap.scaled(
                32,
                32,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
        )
    logo.setToolTip("ScarFall / ScarTools")
    layout.addWidget(logo)

    titles = QtWidgets.QVBoxLayout()
    titles.setSpacing(2)
    title_label = QtWidgets.QLabel(str(title))
    title_label.setObjectName("Title")
    subtitle_label = QtWidgets.QLabel(str(subtitle))
    subtitle_label.setObjectName("Subtitle")
    titles.addWidget(title_label)
    titles.addWidget(subtitle_label)
    layout.addLayout(titles)
    layout.addStretch(1)

    if parent is not None and parent.isWindow():
        enable_rollup(parent)
    return header, subtitle_label


def _layout_widgets(layout):
    """Yield widgets owned by a layout, including widgets in nested layouts."""
    if layout is None:
        return
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        if widget is not None:
            yield widget
            continue
        child_layout = item.layout()
        if child_layout is not None:
            for child_widget in _layout_widgets(child_layout):
                yield child_widget


def enable_rollup(window):
    """Enable native white-title-bar double-click roll-up for a tool window."""
    if getattr(window, "_scartools_rollup_enabled", False):
        return window

    window._scartools_rollup_enabled = True
    window._scartools_rolled_up = False
    window._scartools_rollup_pending = False
    window._scartools_rollup_state = []
    window._scartools_titlebar_filter = _TitleBarRollupEventFilter(window)
    window.installEventFilter(window._scartools_titlebar_filter)
    if sys.platform.startswith("win"):
        _ROLLUP_WINDOWS[int(window.winId())] = window
        _install_native_rollup_filter()
    return window


def toggle_rollup(window):
    """Collapse a ScarTools window to the native title bar or restore it."""
    root_layout = window.layout()
    if root_layout is None:
        return False

    rolled_up = bool(getattr(window, "_scartools_rolled_up", False))
    if not rolled_up:
        state = []
        for widget in _layout_widgets(root_layout):
            state.append((widget, widget.isVisible()))
            widget.hide()

        window._scartools_rollup_state = state
        window._scartools_restore_sizes = (
            QtCore.QSize(window.minimumSize()),
            QtCore.QSize(window.maximumSize()),
            QtCore.QSize(window.size()),
        )
        margins = root_layout.contentsMargins()
        window._scartools_restore_layout = (
            margins.left(),
            margins.top(),
            margins.right(),
            margins.bottom(),
            root_layout.spacing(),
        )
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        window.setMinimumHeight(1)
        window.setMaximumHeight(1)
        window.resize(window.width(), 1)
        window._scartools_rolled_up = True
        return True

    minimum, maximum, size = window._scartools_restore_sizes
    left, top, right, bottom, spacing = window._scartools_restore_layout
    root_layout.setContentsMargins(left, top, right, bottom)
    root_layout.setSpacing(spacing)
    window.setMinimumSize(minimum)
    window.setMaximumSize(maximum)
    for widget, was_visible in window._scartools_rollup_state:
        widget.setVisible(was_visible)
    window.resize(size)
    window._scartools_rolled_up = False
    return False


def create_action_card(
    title,
    description,
    action_text,
    icon_name,
    accent,
    parent=None,
):
    """Create a consistent icon/title/description/action utility card."""
    card = QtWidgets.QFrame(parent)
    card.setObjectName("ActionCard")
    card.setProperty("accent", str(accent))
    card.setMinimumHeight(190)
    card.setSizePolicy(
        QtWidgets.QSizePolicy.Expanding,
        QtWidgets.QSizePolicy.Fixed,
    )
    layout = QtWidgets.QVBoxLayout(card)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(GROUP_SPACING)

    heading = QtWidgets.QHBoxLayout()
    heading.setSpacing(11)
    icon = QtWidgets.QLabel()
    icon.setObjectName("ActionCardIcon")
    icon.setFixedSize(44, 44)
    icon.setAlignment(QtCore.Qt.AlignCenter)
    path = resolve_icon(icon_name)
    if path:
        icon.setPixmap(
            QtGui.QPixmap(path).scaled(
                32,
                32,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
        )
    heading.addWidget(icon)
    copy = QtWidgets.QVBoxLayout()
    copy.setSpacing(3)
    title_label = QtWidgets.QLabel(str(title))
    title_label.setObjectName("ActionCardTitle")
    description_label = QtWidgets.QLabel(str(description))
    description_label.setObjectName("ActionCardDescription")
    description_label.setWordWrap(True)
    description_label.setMinimumHeight(34)
    description_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
    description_label.setSizePolicy(
        QtWidgets.QSizePolicy.Expanding,
        QtWidgets.QSizePolicy.Fixed,
    )
    copy.addWidget(title_label)
    copy.addWidget(description_label)
    heading.addLayout(copy, 1)
    layout.addLayout(heading)
    layout.addStretch(1)

    button = create_button(
        action_text,
        role="primary",
        fixed_width=PRIMARY_BUTTON_WIDTH,
    )
    button.setObjectName("ActionCardButton")
    button.setProperty("accent", str(accent))
    layout.addWidget(button, 0, QtCore.Qt.AlignRight)
    return card, button


def create_stat_card(fields=None, accent="neutral", parent=None):
    """
    Create a standardized Studio Dashboard Stat Card.

    Args:
        fields (list[tuple[str, str, str]], optional): List of (label_text, default_value, color_role).
            Color roles: 'primary', 'blue', 'pipeline', 'success', 'warning', 'error', 'mono', 'muted'.
        accent (str): Department accent or border accent.
        parent (QWidget, optional): Parent Qt widget.

    Returns:
        tuple[QFrame, dict[str, QLabel]]:
            - card_frame: Styled container QFrame conforming to centralized tokens.
            - val_labels: Dictionary mapping field label key to its value QLabel for dynamic updates.
    """
    card = QtWidgets.QFrame(parent)
    card.setObjectName("StatCard")
    card.setProperty("accent", str(accent))

    card_style = "QFrame#StatCard { background: transparent; border: none; }"
    card.setStyleSheet(card_style)

    grid = QtWidgets.QGridLayout(card)
    grid.setContentsMargins(2, 2, 2, 2)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(6)
    grid.setColumnStretch(0, 0)
    grid.setColumnStretch(1, 1)

    val_labels = {}

    color_map = {
        "primary": COLOR_TEXT_PRIMARY,
        "blue": COLOR_PRIMARY_BLUE,
        "pipeline": COLOR_ACCENT_PIPELINE,
        "success": COLOR_STATUS_SUCCESS,
        "warning": COLOR_STATUS_WARNING,
        "error": COLOR_STATUS_ERROR,
        "muted": COLOR_TEXT_MUTED,
    }

    for row_idx, item in enumerate(fields or []):
        if len(item) == 2:
            lbl_text, def_val = item
            role = "primary"
        elif len(item) >= 3:
            lbl_text, def_val, role = item[:3]
        else:
            continue

        lbl = QtWidgets.QLabel(str(lbl_text), card)
        lbl.setStyleSheet("color: {}; font-weight: bold;".format(COLOR_TEXT_MUTED))
        lbl.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)
        lbl.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        val_lbl = QtWidgets.QLabel(str(def_val), card)
        val_lbl.setObjectName("StatCardValue")
        val_lbl.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        val_lbl.setProperty("state", role)
        c_val = color_map.get(role, COLOR_TEXT_PRIMARY)

        if role == "mono":
            val_lbl.setStyleSheet("color: {}; font-family: {}; font-size: 11px;".format(COLOR_TEXT_MUTED, FONT_FAMILY_MONO))
            val_lbl.setWordWrap(True)
        elif role == "primary":
            val_lbl.setStyleSheet("color: {}; font-weight: bold; font-size: 13px;".format(c_val))
        else:
            val_lbl.setStyleSheet("color: {}; font-weight: bold; font-size: 12px;".format(c_val))

        grid.addWidget(lbl, row_idx, 0, QtCore.Qt.AlignLeft)
        grid.addWidget(val_lbl, row_idx, 1)
        val_labels[str(lbl_text)] = val_lbl

    return card, val_labels


class ScarPopupMenu(QtWidgets.QMenu):
    """
    Studio-standard popup context and overflow menu conforming strictly to centralized design tokens.

    Provides:
    - Consistent dark panel background (#292929) and border (#3A3A3A).
    - 6px corner radius and consistent 28-30px item height with centered padding.
    - Anchor alignment method (exec_below_widget) with right/left alignment and vertical gap.
    """

    def __init__(self, parent=None):
        super(ScarPopupMenu, self).__init__(parent)
        self.setObjectName("ScarPopupMenu")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

    def exec_below_widget(self, widget, offset_y=5, align="right"):
        """
        Execute popup menu cleanly positioned below the anchor widget.

        Args:
            widget (QWidget): Target anchor button or widget.
            offset_y (int): Vertical gap below widget (default 5px).
            align (str): 'right' aligns right edge of menu with right edge of widget; 'left' aligns left edge.

        Returns:
            QAction: Selected action or None if dismissed.
        """
        if not widget:
            return self.exec_(QtGui.QCursor.pos())

        self.adjustSize()
        menu_width = max(self.sizeHint().width(), 170)
        widget_rect = widget.rect()
        global_bottom_right = widget.mapToGlobal(QtCore.QPoint(widget_rect.width(), widget_rect.height() + offset_y))
        global_bottom_left = widget.mapToGlobal(QtCore.QPoint(0, widget_rect.height() + offset_y))

        if align == "right":
            pos = QtCore.QPoint(global_bottom_right.x() - menu_width, global_bottom_right.y())
        else:
            pos = global_bottom_left

        return self.exec_(pos)


def create_popup_menu(parent=None):
    """Create a standardized ScarPopupMenu instance conforming to studio design tokens."""
    return ScarPopupMenu(parent=parent)


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class OperationProgressPopup(QtWidgets.QDialog):
    """Modal progress shown only while a Maya operation is running."""

    def __init__(self, title="ScarTools - Processing", parent=None, unit="items"):
        super(OperationProgressPopup, self).__init__(parent)
        register_window(
            getattr(parent, "_scartools_tool_id", "scartools"), self
        )
        self.setWindowTitle(title)
        apply_window_icon(self)
        self.setModal(True)
        self.setWindowModality(QtCore.Qt.WindowModal)
        self.setFixedWidth(460)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        self.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False)
        apply_theme(self)
        self._unit = str(unit or "items")

        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)
        self.title_label = QtWidgets.QLabel("Processing")
        self.title_label.setObjectName("PopupTitle")
        root.addWidget(self.title_label)
        row = QtWidgets.QHBoxLayout()
        self.current_label = QtWidgets.QLabel("Preparing...")
        self.current_label.setObjectName("PopupCurrent")
        self.count_label = QtWidgets.QLabel("")
        self.count_label.setObjectName("PopupCount")
        row.addWidget(self.current_label, 1)
        row.addWidget(self.count_label)
        root.addLayout(row)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setMinimumHeight(24)
        self.progress.setFormat("%p%")
        root.addWidget(self.progress)

        status_row = QtWidgets.QHBoxLayout()
        status_row.setSpacing(GROUP_SPACING)
        self.status_dot = QtWidgets.QLabel("●")
        self.status_dot.setObjectName("PopupStatusDot")
        self.status_dot.setFixedWidth(STATUS_DOT_WIDTH)
        self.status_dot.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label = QtWidgets.QLabel("Starting...")
        self.status_label.setObjectName("PopupStatus")
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_label, 1)
        root.addLayout(status_row)

    def start(self, title, total=0):
        self.title_label.setText(title)
        self.current_label.setText("Preparing...")
        self.count_label.setText(
            "0 / {} {}".format(total, self._unit) if total else ""
        )
        self.progress.setValue(0)
        self.set_status("Starting...", "running")
        self.show()
        self.raise_()
        QtWidgets.QApplication.processEvents()

    def set_current(self, text):
        self.current_label.setText(text or "Processing...")

    def update_progress(self, value, message=None, current=None, total=None):
        self.progress.setValue(max(0, min(100, int(value))))
        if current is not None and total is not None:
            self.count_label.setText(
                "{} / {} {}".format(current, total, self._unit)
            )
        if message:
            self.set_status(message, "running")
        QtWidgets.QApplication.processEvents()

    def set_status(self, text, state="running"):
        self.status_label.setText(str(text))
        self.status_label.setProperty("state", str(state))
        self.status_dot.setProperty("state", str(state))
        repolish(self.status_label)
        repolish(self.status_dot)

    def finish(self, message=None, state="success"):
        self.progress.setValue(100)
        if message:
            self.set_status(message, state)
        QtWidgets.QApplication.processEvents()
        self.close()
        self.deleteLater()


class LogDialog(QtWidgets.QDialog):
    """Color-coded non-modal log viewer bound to a plain-text source widget."""

    def __init__(self, tool_name, source, parent=None):
        super(LogDialog, self).__init__(parent)
        register_window(
            getattr(parent, "_scartools_tool_id", "scartools"), self
        )
        self._source = source
        self.setWindowTitle("{} - Operation Log".format(tool_name))
        apply_window_icon(self)
        apply_theme(self)
        enable_rollup(self)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        configure_window(self, (720, 440), (880, 540))

        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)
        title = QtWidgets.QLabel("Operation Log")
        title.setObjectName("LogDialogTitle")
        clear_button = create_button("Clear Log", fixed_width=90)
        close_button = create_button("Close", fixed_width=CLOSE_BUTTON_WIDTH)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(clear_button)
        header.addWidget(close_button)
        root.addLayout(header)

        self.view = QtWidgets.QTextEdit()
        self.view.setObjectName("ColorLogView")
        self.view.setReadOnly(True)
        self.view.setAcceptRichText(False)
        self.view.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        root.addWidget(self.view, 1)

        clear_button.clicked.connect(self._clear)
        close_button.clicked.connect(self.close)
        source.textChanged.connect(self.refresh)
        self.refresh()

    @staticmethod
    def line_state(line):
        """Classify one log line without relying on color alone."""
        text = str(line or "")
        upper = text.upper()
        if (
            "ERROR:" in upper
            or "CRITICAL:" in upper
            or "EXCEPTION:" in upper
            or "TRACEBACK" in upper
            or "FAILED:" in upper
            or "❌" in text
            or (bool(re.search(r"\bFAILED\b", upper)) and not bool(re.search(r"\b(?:0|NO|NONE|NOT)\s+FAILED\b", upper)))
            or bool(re.search(r"\b[1-9][0-9]*\s+ERROR\(S\)", upper))
            or bool(re.search(r"\b[1-9][0-9]*\s+CRITICAL\b", upper))
        ):
            return "error"
        if any(token in upper for token in (
            "WARNING:", "WARN:", "CAUTION:", "SKIP:", "SKIPPED:", "MISSING:", "BLOCKED:", "ISSUES DETECTED"
        )) or "⚠️" in text or bool(re.search(r"\b[1-9][0-9]*\s+WARNING\(S\)", upper)):
            return "warning"
        if any(token in upper for token in (
            "SUCCESS:", "SUCCESS", "DONE:", "APPLIED:", "COMPLETE", "HEALTHY", "100% CLEAN", "PASSED"
        )) or "✓" in text:
            return "success"
        if any(token in upper for token in (
            "INFO:", "STARTING", "PREPARED:", "REUSED", "CHECKING", "LOADING", "SCANNING", "SCANNED:", "PREFLIGHT"
        )):
            return "info"
        return "default"


    @staticmethod
    def _line_format(state):
        colors = {
            "default": "#C7C7C7",
            "info": "#79A9E6",
            "success": "#72D6AA",
            "warning": "#D6B36A",
            "error": "#F07D7D",
        }
        text_format = QtGui.QTextCharFormat()
        text_format.setForeground(QtGui.QColor(colors.get(state, colors["default"])))
        if state in ("success", "warning", "error"):
            weight = getattr(QtGui.QFont, "DemiBold", None)
            if weight is None and hasattr(QtGui.QFont, "Weight"):
                weight = QtGui.QFont.Weight.DemiBold
            text_format.setFontWeight(weight)
        return text_format

    def refresh(self):
        """Rebuild the view with semantic colors while preserving plain logs."""
        scroll = self.view.verticalScrollBar()
        stay_at_end = scroll.value() >= max(0, scroll.maximum() - 2)
        self.view.clear()
        cursor = self.view.textCursor()
        lines = self._source.toPlainText().splitlines()
        for index, line in enumerate(lines):
            cursor.insertText(line, self._line_format(self.line_state(line)))
            if index != len(lines) - 1:
                cursor.insertBlock()
        if stay_at_end:
            scroll.setValue(scroll.maximum())

    def _clear(self):
        self._source.clear()
        self.refresh()


__all__ = [
    "ACTION_FOOTER_MIN_HEIGHT",
    "CARD_SPACING",
    "CLOSE_BUTTON_WIDTH",
    "FIELD_HEIGHT",
    "FORM_ACTION_WIDTH",
    "FORM_LABEL_WIDTH",
    "GROUP_MARGIN_BOTTOM",
    "GROUP_MARGIN_TOP",
    "GROUP_MARGIN_X",
    "GROUP_SPACING",
    "INLINE_SPACING",
    "LOG_BUTTON_WIDTH",
    "NAV_CONTENT_GAP",
    "LogDialog",
    "OperationProgressPopup",
    "PRIMARY_BUTTON_HEIGHT",
    "PRIMARY_BUTTON_WIDTH",
    "SECONDARY_BUTTON_HEIGHT",
    "SECONDARY_BUTTON_MIN_WIDTH",
    "STATUS_DOT_WIDTH",
    "TABLE_MIN_HEIGHT",
    "TABLE_STATUS_WIDTH",
    "WINDOW_MARGIN",
    "WINDOW_SPACING",
    "configure_button",
    "configure_field",
    "configure_group_layout",
    "configure_root_layout",
    "configure_table",
    "configure_table_columns",
    "configure_window",
    "create_action_card",
    "create_stat_card",
    "ScarPopupMenu",
    "create_popup_menu",
    "create_action_footer",
    "create_brand_header",
    "create_button",
    "create_data_table",
    "create_navigation_tabs",
    "create_operation_group",
    "create_section_panel",
    "create_status_bar",
    "enable_rollup",
    "repolish",
    "toggle_rollup",
]

# Imported last so the base can reuse the completed component surface without
from .window import AboutDialog, BaseToolDialog, close_windows, show_about_dialog
from .license_dialog import LicenseActivationDialog, show_license_dialog
from .logs import FilterChipButton, GlobalLogViewer, GlobalLogWindow, show_global_log
from .toast import ToastWidget, show_toast
from .controls import (
    SegmentedControl,
    create_segmented_control,
    ToggleSwitch,
    create_toggle_switch,
    LabeledSlider,
    create_labeled_slider,
    SearchableComboBox,
    MultiSelectComboBox,
)
from .widgets import (
    Vector3Input,
    create_vector3_input,
    PathPickerWidget,
    create_path_picker,
    UVTileGrid,
    create_uv_tile_grid,
    CurveEditorWidget,
    create_curve_editor,
    PaletteGrid,
    create_palette_grid,
    TokenTagInput,
    create_token_input,
)
from .workspace import (
    StepWizardWidget,
    create_step_wizard,
    PresetManager,
    PresetBar,
    create_preset_bar,
    dock_tool_window,
)
from .theme import (
    THEMES,
    get_available_themes,
    get_active_theme,
    set_active_theme,
)
try:
    from .showcase import (
        DesignSystemShowcaseDialog,
        show_showcase,
    )
except ImportError:
    DesignSystemShowcaseDialog = None
    show_showcase = None
__all__ += [
    "AboutDialog",
    "BaseToolDialog",
    "close_windows",
    "show_about_dialog",
    "LicenseActivationDialog",
    "show_license_dialog",
    "FilterChipButton",
    "GlobalLogViewer",
    "GlobalLogWindow",
    "show_global_log",
    "ToastWidget",
    "show_toast",
    "SegmentedControl",
    "create_segmented_control",
    "ToggleSwitch",
    "create_toggle_switch",
    "LabeledSlider",
    "create_labeled_slider",
    "SearchableComboBox",
    "MultiSelectComboBox",
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
    "StepWizardWidget",
    "create_step_wizard",
    "PresetManager",
    "PresetBar",
    "create_preset_bar",
    "dock_tool_window",
    "THEMES",
    "get_available_themes",
    "get_active_theme",
    "set_active_theme",
    "DesignSystemShowcaseDialog",
    "show_showcase",
]

