# -*- coding: utf-8 -*-
"""Interactive Design System & Component Showcase Dialog for ScarTools."""

from __future__ import absolute_import, division, print_function

from .qt import QtCore, QtGui, QtWidgets, maya_main_window
from .window import BaseToolDialog
from .theme import apply as apply_theme, get_available_themes, set_active_theme
from .controls import (
    create_segmented_control,
    create_toggle_switch,
    create_labeled_slider,
    SearchableComboBox,
    MultiSelectComboBox,
)
from .widgets import (
    create_vector3_input,
    create_path_picker,
    create_uv_tile_grid,
    create_curve_editor,
    create_palette_grid,
    create_token_input,
)
from .workspace import (
    create_step_wizard,
    create_preset_bar,
)
from .tokens import (
    FORM_LABEL_WIDTH,
    INLINE_SPACING,
    FIELD_HEIGHT,
)


class DesignSystemShowcaseDialog(BaseToolDialog):
    """Live interactive showcase window for all centralized ScarTools UI components."""

    OBJECT_NAME = "ScarToolsDesignShowcaseWindow"
    TOOL_ID = "scartools"

    def __init__(self, parent=None):
        super(DesignSystemShowcaseDialog, self).__init__(
            parent if parent is not None else maya_main_window(),
            tool_id=self.TOOL_ID,
        )
        self.setWindowTitle("ScarTools — UI Design System Showcase")
        self.setObjectName(self.OBJECT_NAME)
        
        from . import (
            configure_window,
            configure_root_layout,
            create_brand_header,
            create_section_panel,
            create_action_footer,
        )
        configure_window(self, (820, 680), (960, 800))

        root = QtWidgets.QVBoxLayout(self)
        configure_root_layout(root)

        # 1. Brand Header
        header, _ = create_brand_header(
            "DESIGN SYSTEM SHOWCASE",
            "Interactive gallery of centralized DCC widgets, controls & themes",
            parent=self,
        )
        root.addWidget(header)

        # Scroll area for rich gallery
        scroll = QtWidgets.QScrollArea()
        scroll.setObjectName("TransparentScrollArea")
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Theme Selector Row
        t_panel, t_layout, _ = create_section_panel("Active Studio Theme", accent="pipeline", parent=container)
        t_row = QtWidgets.QHBoxLayout()
        t_lbl = QtWidgets.QLabel("Select Studio Theme:")
        t_lbl.setObjectName("FieldLabel")
        self.theme_combo = QtWidgets.QComboBox()
        for k, name in get_available_themes().items():
            self.theme_combo.addItem(name, k)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        t_row.addWidget(t_lbl)
        t_row.addWidget(self.theme_combo, 1)
        t_layout.addLayout(t_row)
        layout.addWidget(t_panel)

        # 1. Selection Controls & Stepper Panel
        c_panel, c_layout, _ = create_section_panel("Selection & Toggle Controls", accent="modeling", parent=container)
        
        # Segmented Control
        self.seg = create_segmented_control(["Local", "World", "Parent", "Object"], current=0, accent="primary")
        c_layout.addWidget(self.seg)

        # Toggle Switch
        t_row2 = QtWidgets.QHBoxLayout()
        self.toggle = create_toggle_switch("Normalize Skin Weights", checked=True, accent="pipeline")
        t_row2.addWidget(self.toggle)
        t_row2.addStretch(1)
        c_layout.addLayout(t_row2)

        # Labeled Slider
        self.slider = create_labeled_slider("Weight Tolerance", minimum=0.0, maximum=1.0, value=0.05, step=0.01, decimals=2)
        c_layout.addWidget(self.slider)

        # Searchable and MultiSelect Combo
        combo_row = QtWidgets.QHBoxLayout()
        self.search_combo = SearchableComboBox()
        self.search_combo.addItems(["joint_Root", "joint_Spine01", "joint_Spine02", "joint_Arm_L", "joint_Arm_R", "joint_Hand_L", "joint_Hand_R"])
        self.multi_combo = MultiSelectComboBox()
        self.multi_combo.add_items(["hero_body_mesh", "hero_head_mesh", "hero_armor_mesh", "weapon_sword_mesh"])
        combo_row.addWidget(QtWidgets.QLabel("Searchable Dropdown:"))
        combo_row.addWidget(self.search_combo, 1)
        combo_row.addWidget(QtWidgets.QLabel("Multi-Select Dropdown:"))
        combo_row.addWidget(self.multi_combo, 1)
        c_layout.addLayout(combo_row)
        layout.addWidget(c_panel)

        # 2. Specialized DCC Widgets Panel
        w_panel, w_layout, _ = create_section_panel("Specialized DCC Interactive Widgets", accent="rig", parent=container)
        
        # Vector3 Input
        v_row = QtWidgets.QHBoxLayout()
        v_lbl = QtWidgets.QLabel("Offset (X/Y/Z)")
        v_lbl.setFixedWidth(FORM_LABEL_WIDTH + 20)
        self.vec3 = create_vector3_input(0.0, 1.5, -2.0)
        v_row.addWidget(v_lbl)
        v_row.addWidget(self.vec3, 1)
        w_layout.addLayout(v_row)

        # Path Picker
        p_row = QtWidgets.QHBoxLayout()
        p_lbl = QtWidgets.QLabel("Asset File")
        p_lbl.setFixedWidth(FORM_LABEL_WIDTH + 20)
        self.path_picker = create_path_picker(placeholder="Browse or drop .fbx / .ma / .json file...")
        p_row.addWidget(p_lbl)
        p_row.addWidget(self.path_picker, 1)
        w_layout.addLayout(p_row)

        # Token Tag Input
        tag_row = QtWidgets.QHBoxLayout()
        tag_lbl = QtWidgets.QLabel("Asset Tags")
        tag_lbl.setFixedWidth(FORM_LABEL_WIDTH + 20)
        self.tag_input = create_token_input()
        self.tag_input.add_tag("#hero")
        self.tag_input.add_tag("#lod0")
        tag_row.addWidget(tag_lbl)
        tag_row.addWidget(self.tag_input, 1)
        w_layout.addLayout(tag_row)

        # UV Tile Grid & Curve Editor Side by Side
        split_row = QtWidgets.QHBoxLayout()
        
        # UV Grid
        uv_box = QtWidgets.QVBoxLayout()
        uv_lbl = QtWidgets.QLabel("UV Tile Matrix (UDIMs 1001-1040)")
        uv_lbl.setObjectName("SectionSubtitle")
        uv_box.addWidget(uv_lbl)
        self.uv_grid = create_uv_tile_grid(u_count=10, v_count=4)
        self.uv_grid.set_tile_state(1001, "active")
        self.uv_grid.set_tile_state(1002, "active")
        self.uv_grid.set_tile_state(1003, "warning")
        self.uv_grid.set_tile_state(1011, "missing")
        uv_box.addWidget(self.uv_grid)
        split_row.addLayout(uv_box, 1)

        # Curve Editor
        crv_box = QtWidgets.QVBoxLayout()
        crv_lbl = QtWidgets.QLabel("Falloff Curve Editor (Bézier)")
        crv_lbl.setObjectName("SectionSubtitle")
        crv_box.addWidget(crv_lbl)
        self.curve = create_curve_editor()
        self.curve.set_preset("smooth")
        crv_box.addWidget(self.curve)
        split_row.addLayout(crv_box, 1)

        w_layout.addLayout(split_row)

        # Palette Bar
        pal_row = QtWidgets.QHBoxLayout()
        pal_lbl = QtWidgets.QLabel("Color Palette")
        pal_lbl.setFixedWidth(FORM_LABEL_WIDTH + 20)
        self.pal = create_palette_grid()
        pal_row.addWidget(pal_lbl)
        pal_row.addWidget(self.pal)
        pal_row.addStretch(1)
        w_layout.addLayout(pal_row)

        layout.addWidget(w_panel)

        # 3. Workspace, Wizard & Presets Panel
        wk_panel, wk_layout, _ = create_section_panel("Workspace, Wizard & Presets", accent="texturing", parent=container)
        
        # Step Wizard
        self.wizard = create_step_wizard(["1. Select Mesh", "2. Run QA Preflight", "3. Apply Fixers", "4. Export Package"], current=1)
        wk_layout.addWidget(self.wizard)

        # Preset Bar
        self.preset_bar = create_preset_bar(tool_id="showcase_demo")
        wk_layout.addWidget(self.preset_bar)

        layout.addWidget(wk_panel)

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # Standard Action Footer
        footer, self.msg_lbl, self.action_btn, self.status_dot, self.status_lbl, _, _ = create_action_footer(
            "TEST PIPELINE ACTION",
            message="Ready • All components connected",
            parent=self,
        )
        self.action_btn.clicked.connect(self._on_action_clicked)
        root.addWidget(footer)

    def _on_theme_changed(self, idx):
        theme_key = self.theme_combo.itemData(idx)
        if theme_key:
            set_active_theme(theme_key)
            apply_theme(self, theme_name=theme_key)

    def _on_action_clicked(self):
        from ..framework.benchmark import ExecutionTimer
        with ExecutionTimer(operation_name="Showcase Demo Action", item_count=len(self.uv_grid.selected_udims())):
            self.status_dot.setObjectName("SuccessLabel")
            self.status_dot.setText("● Success")


_showcase_window_instance = None


def show_showcase(parent=None):
    """Open or focus the ScarTools Design System Showcase Dialog."""
    global _showcase_window_instance
    try:
        if _showcase_window_instance is not None and _showcase_window_instance.isVisible():
            _showcase_window_instance.raise_()
            _showcase_window_instance.activateWindow()
            return _showcase_window_instance
    except Exception:
        _showcase_window_instance = None

    win = DesignSystemShowcaseDialog(parent=parent or maya_main_window())
    _showcase_window_instance = win
    win.show()
    return win


__all__ = ["DesignSystemShowcaseDialog", "show_showcase"]
